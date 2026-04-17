# mypy: ignore-errors

import glob
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path
from typing import Any, Iterable, Literal, Union

import esmpy
import numpy as np
import pandas as pd
import xarray as xr
from pydantic import BaseModel

from regrid_wrapper.app.chem_regrid.context import ChemRegridContext
from regrid_wrapper.app.chem_regrid.dataset.model import DatasetName, InterpMethod
from regrid_wrapper.context.comm import COMM, reconcile_bounds
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.esmpy.field_wrapper import (
    Dimension,
    DimensionCollection,
    FieldWrapper,
    GridSpec,
    GridWrapper,
    HasNcAttrsType,
    NcToField,
    NcToGrid,
    copy_nc_variable,
    open_nc,
    set_variable_data,
)

_LOGGER = LOGGER.getChild("mpas-regrid")


# Try to find the latest RAVE file available up to max_lookback_hours before target_time_str
# to avoid setting zeroes when a particular hour file is missing.
def find_latest_src_file(input_dir, target_time_str, ebb_dcycle, dataset_name, max_lookback_hours=24):
    """Return list of files for the latest time <= target_time_str."""
    fmt = "%Y%m%d%H"  # RAVE
    fmt2 = "%Y%j%H"  # GOES
    target_time = datetime.strptime(target_time_str, fmt)

    input_dir_str = str(input_dir)

    for h in range(max_lookback_hours + 1):
        if ebb_dcycle == -1 or ebb_dcycle == 2:
            this_time = target_time - timedelta(hours=h)
        elif ebb_dcycle == 1:
            this_time = target_time + timedelta(hours=h)
        else:
            _LOGGER.warning("unrecognized ebb_dcycle, reverting to same-day, ebb_dcycle = 1")
            this_time = target_time + timedelta(hours=h)

        if dataset_name == "RAVE":
            this_str = this_time.strftime(fmt)
            paths = glob.glob(input_dir_str + "/RAVE-HrlyEmiss-3km_v2r0_blend_s" + this_str + "*")
        elif dataset_name == "GOES":
            this_str = this_time.strftime(fmt2)
            paths = glob.glob(input_dir_str + "/OR_ABI-L2-AODC-M6_G18_s" + this_str + "*")
        if paths:
            if h > 0:
                _LOGGER.warning(f"Missing {dataset_name} file for {target_time_str}, using {this_str} instead")
            return paths
    # nothing found within lookback window
    return []


#
def create_ngfs_sparse_mesh(lat_1d, lon_1d, resolution=0.01):
    """
    Creates an esmpy.Mesh dynamically from 1-D point source data.
    Calculates the 4 corners of a square cell of size `resolution`
    around each center point in memory.
    This is the best approach since NGFS data are point-source (1-D),
    but we rarely have more than 1000 fires in the domain, so we
    can afford to keep this in memory instead of creating a file.
    """

    num_cells = len(lat_1d)
    if num_cells == 0:
        return None

    num_nodes = num_cells * 4
    d = resolution / 2.0

    node_lons = np.column_stack([lon_1d - d, lon_1d + d, lon_1d + d, lon_1d - d]).flatten()

    node_lats = np.column_stack([lat_1d - d, lat_1d - d, lat_1d + d, lat_1d + d]).flatten()

    node_coords = np.empty(num_nodes * 2, dtype=np.float64)
    node_coords[0::2] = node_lons
    node_coords[1::2] = node_lats

    node_ids = np.arange(1, num_nodes + 1, dtype=np.int32)
    node_owners = np.full(num_nodes, COMM.rank, dtype=np.int32)

    element_ids = np.arange(1, num_cells + 1, dtype=np.int32)
    element_types = np.full(num_cells, esmpy.MeshElemType.QUAD, dtype=np.int32)

    # CRITICAL FIX: esmpy expects 0-based indexing for connectivity!
    element_conn = np.arange(0, num_nodes, dtype=np.int32)

    # Explicitly set spherical coordinates
    mesh = esmpy.Mesh(parametric_dim=2, spatial_dim=2, coord_sys=esmpy.CoordSys.SPH_DEG)

    mesh.add_nodes(node_count=num_nodes, node_ids=node_ids, node_coords=node_coords, node_owners=node_owners)

    mesh.add_elements(element_count=num_cells, element_ids=element_ids, element_types=element_types, element_conn=element_conn)

    return mesh


#
class AbstractSrcField(ABC, BaseModel):
    name: str
    attrs: dict[str, Any]
    fill_value: float
    dtype: Any
    num_cells: int
    level_out_name: str | None
    level_out_size: int
    time_size: int

    @cached_property
    def time_dimension(self) -> Dimension:
        return Dimension(
            name=("Time",),
            size=self.time_size,
            lower=0,
            upper=self.time_size,
            staggerloc=esmpy.StaggerLoc.CENTER,
            coordinate_type="time",
        )

    @cached_property
    def nklevel_dimension(self) -> Dimension:
        return Dimension(
            name=(self.level_out_name,),
            size=self.level_out_size,
            lower=0,
            upper=self.level_out_size,
            staggerloc=esmpy.StaggerLoc.CENTER,
            coordinate_type="level",
        )

    def create_ncells_dimension(self, bounds: tuple[int, int]) -> Dimension:
        return Dimension(
            name=("nCells",),
            size=self.num_cells,  # 225636, #130333,  # tdk: pull from origin,
            lower=bounds[0],
            upper=bounds[1],
            staggerloc=esmpy.MeshLoc.ELEMENT,
            coordinate_type="cell",
        )

    @abstractmethod
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection: ...

    @abstractmethod
    def reshape_field_data(self, target: np.ndarray) -> np.ndarray: ...


class SrcField2d(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(value=(self.create_ncells_dimension(ncells_bounds),))

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1)


class SrcField2d_plusTime(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(value=(self.time_dimension, self.create_ncells_dimension(ncells_bounds)))

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(self.time_size, -1)


class SrcField3d(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(
            value=(
                self.create_ncells_dimension(ncells_bounds),
                self.nklevel_dimension,
            )
        )

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1, self.level_out_size)


class SrcField3d_plusTime(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(
            value=(
                self.create_ncells_dimension(ncells_bounds),
                self.nklevel_dimension,
                self.time_dimension,
            )
        )

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1, self.level_out_size, self.time_size)


class DatasetRegridContext(BaseModel):
    dataset_name: DatasetName
    workdir: Path
    src_path: Path
    dst_path: Path
    new_dst_path: Path
    desc_stats_out: Path
    weight_path: Path
    InterpMethod: InterpMethod
    scrip_path: Path
    num_cells: int
    mesh_name: str
    field_names: tuple
    x_center: str
    y_center: str
    x_dim: str
    y_dim: str
    x_corner: Union[str, None]
    y_corner: Union[str, None]
    x_corner_dim: Union[str, None]
    y_corner_dim: Union[str, None]
    level_in_name: str | None
    # level_in_size: int
    level_out_name: str | None
    level_out_size: int
    time_name: str | None
    time_size: int
    # InterpMask: float
    write_desc_stats: bool = False

    rank: int = COMM.rank

    @cached_property
    def src_fields(self) -> tuple[AbstractSrcField, ...]:
        src_fields = []
        with open_nc(self.src_path, mode="r") as ds:
            for field_name in self.field_names:
                read_name = field_name
                if self.dataset_name == "NGFS" and field_name == "PM25":
                    read_name = "EMIS_PM25"

                if read_name not in ds.variables:
                    raise KeyError(f"Source variable '{read_name}' not found for field '{field_name}' in {self.src_path}")
                var = ds.variables[read_name]
                init_data = {
                    "name": field_name,
                    "attrs": self._get_nc_attrs_(var),
                    "fill_value": -1.0,
                    "dtype": var.dtype,
                    "level_out_name": self.level_out_name,
                    "level_out_size": self.level_out_size,
                    "time_size": self.time_size,
                    "num_cells": self.num_cells,
                }
                if self.level_out_size == 0:
                    if self.time_size == 0:
                        app = SrcField2d.model_validate(init_data)
                    else:
                        app = SrcField2d_plusTime.model_validate(init_data)
                else:
                    if self.time_size == 0:
                        app = SrcField3d.model_validate(init_data)
                    else:
                        app = SrcField3d_plusTime.model_validate(init_data)
                src_fields.append(app)
        _LOGGER.debug(f"{src_fields=}")
        return tuple(src_fields)

    @staticmethod
    def _get_nc_attrs_(src: HasNcAttrsType) -> dict[str, Any]:
        exclude = ("coordinates", "valid_range")
        return {ii: getattr(src, ii) for ii in src.ncattrs() if not ii.startswith("_") and ii not in exclude}


class FileDesc(BaseModel):
    path: Path
    origin: Literal["src", "dst"]
    field_names: tuple[str, ...]


class ChemRegridProcessor:
    _dst_mesh: esmpy.Mesh | None = None

    def __init__(self, context: DatasetRegridContext) -> None:
        self.context = context

        self._regridder: esmpy.Regrid | None = None
        self._dst_field: esmpy.Field | None = None
        self._src_gwrap: GridWrapper | None = None

    def initialize(self) -> None:
        _LOGGER.info(f"initialize: {self.context=}")
        esmpy.Manager(debug=True)

        # JLS - temporary fix for coords not in file
        if self.context.dataset_name == "GOES":
            pathsrc = self.context.workdir / "goes19_abi_conus_interpolated_lat_lon.nc"
        else:
            pathsrc = self.context.src_path

        _LOGGER.info("create source grid")
        self._src_gwrap = NcToGrid(
            path=pathsrc,
            spec=GridSpec.model_validate(self.context.model_dump()),
        ).create_grid_wrapper()

        _LOGGER.info("create source field")
        src_fwrap = self.create_src_field_wrapper(self.context.src_fields[0].name)

        if self._dst_mesh is None:
            _LOGGER.info("create destination mesh")
            # dst_mesh = esmpy.Mesh(
            #     filename=str(self.context.scrip_path), filetype=esmpy.FileFormat.SCRIP
            # )
            self._dst_mesh = esmpy.Mesh(
                filename=str(self.context.scrip_path), filetype=esmpy.FileFormat.UGRID, meshname="grid_topology"
            )
        dst_mesh = self._dst_mesh

        self._dst_field = self._create_dst_field_(dst_mesh)
        self._regridder = self._create_regridder_(src_fwrap)

    def _create_dst_field_(self, dst_mesh: esmpy.Mesh) -> esmpy.Field:
        _LOGGER.info("create destination field")

        # Check for extra dims beyond lat/lon
        ndbounds = []
        if self.context.level_out_size > 0:
            ndbounds.append(self.context.level_out_size)
        if self.context.time_size > 0:
            ndbounds.append(self.context.time_size)

        kwargs = {}
        if ndbounds:
            kwargs["ndbounds"] = tuple(ndbounds)

        return esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, **kwargs)

    def _create_regridder_(self, src_fwrap: FieldWrapper) -> esmpy.RegridFromFile | esmpy.Regrid:
        _LOGGER.info("create regridder")
        if self.context.weight_path.exists():
            _LOGGER.info("create regridder from file")
            regridder = esmpy.RegridFromFile(
                srcfield=src_fwrap.value,
                dstfield=self._dst_field,
                filename=str(self.context.weight_path),
            )
        else:
            _LOGGER.info("create regridder in-memory")
            method_map = {
                InterpMethod.CONSERVE: esmpy.RegridMethod.CONSERVE,
                InterpMethod.CONSERVE_2ND: esmpy.RegridMethod.CONSERVE_2ND,
                InterpMethod.BILINEAR: esmpy.RegridMethod.BILINEAR,
                InterpMethod.NEAREST_STOD: esmpy.RegridMethod.NEAREST_STOD,
            }
            # Default to NEAREST_STOD if not found in map (preserving original behavior)
            regrid_method = method_map[self.context.InterpMethod]

            _LOGGER.info(f"using {regrid_method} interp")
            regridder = esmpy.Regrid(
                srcfield=src_fwrap.value,
                dstfield=self._dst_field,
                regrid_method=regrid_method,
                unmapped_action=esmpy.UnmappedAction.IGNORE,
                ignore_degenerate=True,
                large_file=True,
                filename=str(self.context.weight_path),
            )
        return regridder

    def run(self) -> None:
        _LOGGER.info("apply regridding")

        _LOGGER.info("create output file")
        if self.context.rank == 0:
            with open_nc(self.context.new_dst_path, mode="w", clobber=True, parallel=False) as dst_nc:
                dst_nc.createDimension("nCells", self.context.num_cells)
                if self.context.level_out_name is not None:
                    dst_nc.createDimension(self.context.level_out_name, self.context.level_out_size)
                dst_nc.createDimension("StrLen", 64)
                if self.context.time_size > 1:
                    dst_nc.createDimension("Time", self.context.time_size)
                elif self.context.time_size == 1:
                    if "Time" not in dst_nc.dimensions:
                        dst_nc.createDimension("Time")
                    else:
                        _LOGGER.info("Not creating a time dimension")
                dst_nc.setncattr("created_at", str(datetime.now(timezone.utc)))
                dst_nc.setncattr("src_path", str(self.context.src_path))
                dst_nc.setncattr("dst_path", str(self.context.dst_path))

                with open_nc(self.context.dst_path, mode="r", parallel=False) as src_nc:
                    if self.context.dataset_name in ("RAVE"):
                        for varname in ("latCell", "lonCell", "areaCell", "xtime"):
                            copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)
                    elif self.context.dataset_name in ("FENGSHA_2D"):
                        for varname in ("latCell", "lonCell"):
                            copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)
                    else:
                        for varname in ("latCell", "lonCell", "xtime"):
                            copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)

        regridder = self.get_regridder()
        for src_field in self.context.src_fields:
            _LOGGER.info(f"regridding {src_field.name=}")
            src_fwrap = self.create_src_field_wrapper(field_name=src_field.name)

            dst_field = self.get_dst_field()
            dst_field.data.fill(0.0)
            regridder(src_fwrap.value, dst_field)

            local_bounds = (dst_field.lower_bounds[0], dst_field.upper_bounds[0])
            reconciled_bounds = reconcile_bounds(local_bounds)
            dims = src_field.create_dimension_collection(reconciled_bounds)
            _LOGGER.info(f"{dims=}")
            _LOGGER.info("writing field to netcdf")
            with open_nc(self.context.new_dst_path, mode="a") as ds:
                if self.context.dataset_name == "RAVE" and src_field.name in ("FRP_MEAN", "FRE"):
                    area = np.asarray(ds.variables["areaCell"])
                    area_subset = area[reconciled_bounds[0] : reconciled_bounds[1]].reshape(dims.shape_local)
                _LOGGER.info(f"creating variable {src_field.name=}")
                var = ds.createVariable(
                    src_field.name,
                    src_field.dtype,
                    [dim.name[0] for dim in dims.value],
                    fill_value=src_field.fill_value,
                )
                # Don't carry over fill value and datatype
                if self.context.dataset_name != "GOES":
                    for k, v in src_field.attrs.items():
                        setattr(var, k, v)

                _LOGGER.info(f"setting variable data {src_field.name=}")
                # Multiply FRE/FRP by output area so it is back to W or J*s
                if self.context.dataset_name == "RAVE" and src_field.name in ("FRP_MEAN", "FRE"):
                    set_variable_data(
                        var,
                        dims,
                        src_field.reshape_field_data(dst_field.data * area_subset),
                        collective=True,
                    )
                else:
                    set_variable_data(
                        var,
                        dims,
                        src_field.reshape_field_data(dst_field.data),
                        collective=True,
                    )
            _LOGGER.info(f"finished writing field to netcdf {src_field.name=}")
            src_fwrap.value.destroy()
            del src_fwrap

            if src_field.name == "ENL_POLL":
                with open_nc(self.context.new_dst_path, mode="a") as ds:
                    _LOGGER.info("renaming and combining tree fields")

                    src_fwrap_enl = self.create_src_field_wrapper(field_name="ENL_POLL")
                    dst_field_enl = self.get_dst_field()
                    dst_field_enl.data.fill(0.0)
                    regridder(src_fwrap_enl.value, dst_field_enl)

                    src_fwrap_dbl = self.create_src_field_wrapper(field_name="DBL_POLL")
                    dst_field_dbl = self.get_dst_field()
                    dst_field_dbl.data.fill(0.0)
                    regridder(src_fwrap_dbl.value, dst_field_dbl)

                    src_field = self.context.src_fields[0]

                    var = ds.createVariable(
                        "TREE_POLL",
                        src_field.dtype,
                        [dim.name[0] for dim in dims.value],
                        fill_value=src_field.fill_value,
                    )
                    for k, v in self.context.src_fields[0].attrs.items():
                        setattr(var, k, v)
                    set_variable_data(
                        var,
                        dims,
                        src_field.reshape_field_data(dst_field_enl.data + dst_field_dbl.data),
                        collective=True,
                    )
                src_fwrap_enl.value.destroy()
                del src_fwrap_enl
                src_fwrap_dbl.value.destroy()
                del src_fwrap_dbl
            if src_field.name == "TPM":
                with open_nc(self.context.new_dst_path, mode="a") as ds:
                    _LOGGER.info("calculating PM10 as TPM - PM25")
                    src_fwrap_ttl = self.create_src_field_wrapper(field_name="TPM")
                    src_fwrap_p25 = self.create_src_field_wrapper(field_name="PM25")

                    dst_field_ttl = self.get_dst_field()
                    dst_field_ttl.data.fill(0.0)
                    regridder(src_fwrap_ttl.value, dst_field_ttl)

                    dst_field_p25 = self.get_dst_field()
                    dst_field_p25.data.fill(0.0)
                    regridder(src_fwrap_p25.value, dst_field_p25)

                    src_field = self.context.src_fields[0]

                    var = ds.createVariable(
                        "PM10",
                        src_field.dtype,
                        [dim.name[0] for dim in dims.value],
                        fill_value=src_field.fill_value,
                    )
                    for k, v in self.context.src_fields[0].attrs.items():
                        setattr(var, k, v)
                    data1 = src_field.reshape_field_data(dst_field_ttl.data)
                    data2 = src_field.reshape_field_data(dst_field_p25.data)
                    data3 = data1 - data2
                    set_variable_data(
                        var,
                        dims,
                        data3,
                        collective=True,
                    )
                src_fwrap_ttl.value.destroy()
                del src_fwrap_ttl
                src_fwrap_p25.value.destroy()
                del src_fwrap_p25

        if self.context.write_desc_stats and self.context.rank == 0:
            field_names = tuple(ii.name for ii in self.context.src_fields)
            targets = [
                FileDesc(
                    path=self.context.new_dst_path,
                    origin="dst",
                    field_names=field_names,
                ),
                FileDesc(
                    path=self.context.src_path,
                    origin="src",
                    field_names=field_names,
                ),
            ]
            data_frame = self.create_desc_stuff(targets)
            data_frame.to_csv(self.context.desc_stats_out, index=False)

    def finalize(self) -> None:
        _LOGGER.info("finalizing")
        self._regridder.destroy()
        self._dst_field.destroy()
        self._src_gwrap.value.destroy()
        # self._dst_mesh.destroy()

    def create_desc_stuff(self, targets: Iterable[FileDesc]) -> pd.DataFrame:
        _LOGGER.info("entering create_desc_stuff")
        if self.context.rank > 0:
            raise ValueError

        to_concat = []
        for target in targets:
            with open_nc(target.path, mode="r", parallel=False) as ds:
                for varname in target.field_names:
                    data = ds.variables[varname][:].filled(np.nan).ravel()
                    data_frame = pd.DataFrame.from_dict({varname: data})
                    desc = data_frame.describe()
                    adds = {
                        varname: [
                            data_frame[varname].sum(),
                            data_frame[varname].isnull().sum(),
                            target.origin,
                            target.path,
                        ]
                    }
                    desc = pd.concat(
                        [
                            desc,
                            pd.DataFrame(data=adds, index=["sum", "count_null", "origin", "path"]),
                        ]
                    )
                    to_concat.append(desc)
        ret = pd.concat([ii.transpose() for ii in to_concat])
        ret.index.name = "field_name"
        ret.reset_index(inplace=True)
        _LOGGER.info("exiting create_desc_stuff")
        return ret

    def create_src_field_wrapper(self, field_name: str) -> FieldWrapper:
        _LOGGER.info("create source field")
        src_fwrap = self._create_raw_src_field_wrapper_(field_name)

        # Get the area from the RAVE file, need to convert from /grid to /m2
        if self.context.dataset_name == "RAVE" and field_name in (
            "PM25",
            "NH3",
            "SO2",
            "FRE",
            "FRP_MEAN",
            "TPM",
            "CH4",
            "CO",
            "NOx",
        ):
            area_fwrap = NcToField(
                path=self.context.src_path,
                name="area",
                gwrap=self.get_src_gwrap(),
                dim_time=None,
            ).create_field_wrapper()
            area_data = area_fwrap.value.data

        # GRA2PES PM, convert from metric tons/km2/hr to ug/m2/s
        if self.context.dataset_name == "GRA2PES" and field_name in ("PM25-PRI", "PM10-PRI"):
            conv_aer = 1.0e6 / 3600.0
        # GRA2PES methane, convert from moles/km2/hr to ug/m2/s
        elif self.context.dataset_name == "GRA2PES" and field_name in ("HC01", "SO2", "CO", "NH3", "NOX"):
            conv_aer = 1.0e-6 / 3600.0
        # RAVE methane, convert from kg/hr to mol/m2/s
        elif self.context.dataset_name == "RAVE":
            if field_name == "CH4":
                conv_aer = (1.0 / 16.0) * 1000.0
            elif field_name == "CO":
                conv_aer = (1.0 / 28.0) * 1000.0
            elif field_name == "NH3":
                conv_aer = (1.0 / 17.0) * 1000.0
            elif field_name == "NOx":
                conv_aer = ((1.0 / 30.0) + (1.0 / 46.0)) / 2.0 * 1000.0
            else:
                conv_aer = 1.0
        elif self.context.dataset_name == "NEMO_RWC" and field_name in ("PEC", "POC", "PMOTHR", "PMC"):
            # Convert g/s/km2 (on 1km grid) to ug/m2/s -->
            conv_aer = 1.0
        elif self.context.dataset_name == "NEMO_ANTHRO" and field_name in ("PEC", "POC", "PMOTHR", "PMC"):
            # Convert g/s/km2 to ug/m2/s -->
            conv_aer = 1.0
        else:
            conv_aer = 1.0

        src_data = src_fwrap.value.data
        if self.context.dataset_name == "RAVE" and field_name in ("PM25", "TPM"):
            # If RAVE aerosol emissions, convert from kg/hr to ug/m2/s
            src_data[:] = np.where(src_data < 0.0, 0.0, src_data * 1.0e3 / area_data[:, :, np.newaxis] / 3600.0)
        elif self.context.dataset_name == "RAVE" and field_name in ("CH4", "NH3", "SO2", "CO", "NOx"):
            # If RAVE gas emissions, convert from kg/hr to mol/m2/s
            src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data / area_data[:, :, np.newaxis] / 3600.0)
        elif self.context.dataset_name == "RAVE" and field_name in ("FRE", "FRP_MEAN"):
            # For FRE, FRP, don't multiply area by 1.e6, cancelled out by MW to W conversion
            src_data[:] = np.where(src_data < 0.0, 0.0, src_data / (area_data[:, :, np.newaxis]))
        else:
            src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)

        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)
        return src_fwrap

    def _create_raw_src_field_wrapper_(self, field_name: str) -> FieldWrapper:
        if self.context.dataset_name == "GRA2PES" and field_name == "h_agl":
            dim_level = ("bottom_top_stag",)
        else:
            dim_level = (self.context.level_in_name,) if self.context.level_in_name else None

        dim_time = (self.context.time_name,) if self.context.time_name else None

        return NcToField(
            path=self.context.src_path,
            name=field_name,
            gwrap=self.get_src_gwrap(),
            dim_time=dim_time,
            dim_level=dim_level,
        ).create_field_wrapper()

    def get_src_gwrap(self) -> GridWrapper:
        if self._src_gwrap is None:
            raise ValueError
        return self._src_gwrap

    def get_dst_field(self) -> esmpy.Field:
        if self._dst_field is None:
            raise ValueError
        return self._dst_field

    def get_regridder(self) -> esmpy.Regrid:
        if self._regridder is None:
            raise ValueError
        return self._regridder

    def init_destination_only(self) -> None:
        """Loads the heavy MPAS destination mesh once for dynamic NGFS processing."""
        _LOGGER.info("Initializing MPAS Destination Mesh (Once)")
        esmpy.Manager(debug=True)

        # if not self.context.scrip_path.exists() and self.context.rank == 0:
        #     _LOGGER.info("writing mpas scrip grid")
        #     mpas_desc = MpasCellMeshDescriptor(
        #         str(self.context.dst_path), self.context.mesh_name + ".init"
        #     )
        #     mpas_desc.to_scrip(str(self.context.scrip_path))

        _LOGGER.info("create destination mesh")
        dst_mesh = esmpy.Mesh(filename=str(self.context.scrip_path), filetype=esmpy.FileFormat.UGRID, meshname="grid_topology")

        # Create destination field (using logic from your original initialize method)
        if self.context.level_out_size > 1 and self.context.time_size > 1:
            self._dst_field = esmpy.Field(
                dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, ndbounds=(self.context.level_out_size, self.context.time_size)
            )
        elif self.context.level_out_size > 1 and self.context.time_size == 1:
            self._dst_field = esmpy.Field(
                dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, ndbounds=(self.context.level_out_size,)
            )
        elif self.context.level_out_size == 1 and self.context.time_size > 1:
            self._dst_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, ndbounds=(self.context.time_size,))
        else:
            self._dst_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT)

    def process_ngfs_file(self, file_path: Path, resolution: float = 0.01) -> None:
        """Dynamically builds a mesh for NGFS points, regrids, and writes the output."""
        _LOGGER.info(f"Processing NGFS file: {file_path}")

        # 1. Read NGFS Coordinates AND Area
        with open_nc(file_path, mode="r") as ds:
            lats = ds.variables["lat"][:].filled(np.nan)
            lons = ds.variables["lon"][:].filled(np.nan)

            # Read the NGFS area (in km2)
            if "GRID_AREA" in ds.variables:
                grid_area = ds.variables["GRID_AREA"][:].filled(np.nan)
            else:
                _LOGGER.warning("GRID_AREA not found! Defaulting to 1.0 km2.")
                grid_area = np.ones_like(lats)

        # Filter out NaNs
        valid = ~np.isnan(lats) & ~np.isnan(lons) & ~np.isnan(grid_area)
        lats = lats[valid]
        lons = lons[valid]
        grid_area = grid_area[valid]

        # CRITICAL FIX: Convert -180/180 to 0/360 to match MPAS grid
        lons = lons % 360.0

        if len(lats) == 0:
            _LOGGER.warning("No valid fires in file.")
            return

        # 2. Build Sparse Source Mesh
        src_mesh = create_ngfs_sparse_mesh(lats, lons, resolution)
        if src_mesh is None:
            return

        # 3. Create Output NetCDF File (Header Info)
        if self.context.rank == 0:
            with open_nc(self.context.new_dst_path, mode="w", clobber=True, parallel=False) as dst_nc:
                dst_nc.createDimension("nCells", self.context.num_cells)
                dst_nc.createDimension(self.context.level_out_name, self.context.level_out_size)
                dst_nc.createDimension("StrLen", 64)
                if self.context.time_size > 1:
                    dst_nc.createDimension("Time", self.context.time_size)
                elif self.context.time_size == 1:
                    dst_nc.createDimension("Time")
                dst_nc.setncattr("created_at", str(datetime.now(timezone.utc)))
                dst_nc.setncattr("src_path", str(self.context.src_path))
                dst_nc.setncattr("dst_path", str(self.context.dst_path))

                # Copy base MPAS variables
                with open_nc(self.context.dst_path, mode="r", parallel=False) as src_nc:
                    for varname in ("latCell", "lonCell", "areaCell", "xland", "xtime"):
                        copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)

        # 4. Process Each Variable
        for src_field in self.context.src_fields:
            _LOGGER.info(f"regridding NGFS {src_field.name=}")

            # Create Source Field dynamically
            src_field = esmpy.Field(src_mesh, name=src_field.name, meshloc=esmpy.MeshLoc.ELEMENT)

            # Map MPAS expected name to NGFS actual name
            if src_field.name == "PM25":
                ngfs_var_name = "EMIS_PM25"
            else:
                ngfs_var_name = src_field.name

            # Load the raw data
            with open_nc(file_path, mode="r") as ds:
                if ngfs_var_name in ds.variables:
                    raw_data = ds.variables[ngfs_var_name][:].filled(0.0)[valid]
                else:
                    _LOGGER.warning(f"Variable {ngfs_var_name} not found! Skipping.")
                    continue

            # ---------------------------------------------------------
            # UNIT CONVERSIONS (Identical to RAVE logic)
            # ---------------------------------------------------------
            if src_field.name in ("PM25", "TPM"):
                # Convert from kg/hr to ug/m2/s (1e3 handles the km2 to m2 and kg to ug ratio)
                src_data = np.where(raw_data < 0.0, 0.0, raw_data * 1.0e3 / grid_area / 3600.0)
            elif src_field.name in ("FRE", "FRP_MEAN"):
                # For FRE, FRP: MW to W (1e6) cancels out with km2 to m2 (1e6)
                src_data = np.where(raw_data < 0.0, 0.0, raw_data / grid_area)
            else:
                src_data = np.where(raw_data < 0.0, 0.0, raw_data)

            src_field.data[:] = src_data

            # Create Dynamic Regridder
            regridder = esmpy.Regrid(
                srcfield=src_field,
                dstfield=self._dst_field,
                regrid_method=esmpy.RegridMethod.CONSERVE,
                unmapped_action=esmpy.UnmappedAction.IGNORE,
            )

            # Apply Regridding
            self._dst_field.data.fill(0.0)
            regridder(src_field, self._dst_field)

            # Write to Output NetCDF
            local_bounds = (self._dst_field.lower_bounds[0], self._dst_field.upper_bounds[0])
            reconciled_bounds = reconcile_bounds(local_bounds)
            dims = src_field.create_dimension_collection(reconciled_bounds)

            with open_nc(self.context.new_dst_path, mode="a") as ds:
                var = ds.createVariable(
                    src_field.name,  # Keep it as standard name in output!
                    src_field.dtype,
                    [dim.name[0] for dim in dims.value],
                    fill_value=src_field.fill_value,
                )
                for k, v in src_field.attrs.items():
                    setattr(var, k, v)

                # Multiply by areaCell for Power/Energy variables (back to total W in cell)
                if src_field.name in ("FRP_MEAN", "FRE"):
                    area = np.asarray(ds.variables["areaCell"])
                    area_subset = area[reconciled_bounds[0] : reconciled_bounds[1]]
                    set_variable_data(var, dims, src_field.reshape_field_data(self._dst_field.data * area_subset), collective=True)
                else:
                    set_variable_data(var, dims, src_field.reshape_field_data(self._dst_field.data), collective=True)

            # Clean up memory
            regridder.destroy()
            src_field.destroy()

        # Clean up mesh
        src_mesh.destroy()


def main(ctx: ChemRegridContext) -> None:
    YYYY = ctx.cycle[0:4]
    MM = ctx.cycle[4:6]
    DD = ctx.cycle[6:8]
    HH = ctx.cycle[8:10]
    x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0)
    JJJ = x.strftime("%j")
    DOWh = int(x.strftime("%u"))
    if DOWh <= 5:
        DOWs = "weekdy"
    elif DOWh == 6:
        DOWs = "satdy"
    else:
        DOWs = "sundy"

    # Calculate the number of cells in the
    with open_nc(ctx.dst_path, mode="r", parallel=False) as src_nc:
        foo = src_nc.variables["latCell"]
        num_cells = len(foo)
        # xland = src_nc.variables['xland']
        # lmask[:] = np.where(xland > 0,1,0)

    if ctx.dataset_name == "RAVE":
        # JLS, TODO - NEED TO ACCOUNT FOR EBB1, MORE THAN 24, ETC.
        # Determine the cycle dates to process +%Y%m%d%H
        dates_needed = []
        for i in range(25):
            if ctx.ebb_dcycle == 1:  # Same-day emissions
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) + timedelta(hours=i)
            elif ctx.ebb_dcycle == -1 or ctx.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) - timedelta(hours=i)
            else:
                _LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) + timedelta(hours=i)

            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)

    elif ctx.dataset_name == "NGFS":
        # Determine the cycle dates to process +%Y%m%d%H
        # This is for RETROS (using current datetime, not day before)
        dates_needed = []
        for i in range(25):  # GAF retro current day emissions
            if ctx.ebb_dcycle == 1:  # Same-day emissions
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) + timedelta(hours=i)
            elif ctx.ebb_dcycle == -1 or ctx.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) - timedelta(hours=i)
            else:
                _LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) + timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
    elif ctx.dataset_name == "FMC":  # fuel moisture content
        dates_needed = []
        for i in range(25):
            x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) - timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
    elif ctx.dataset_name == "GOES":
        dates_needed = []
        for i in range(25):
            if ctx.ebb_dcycle == 1:  # Same-day emissions
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) + timedelta(hours=i)
            elif ctx.ebb_dcycle == -1 or ctx.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) - timedelta(hours=i)
            else:
                _LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = datetime(int(YYYY), int(MM), int(DD), int(HH), 0, 0) - timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)

    regrid_context = DatasetRegridContext(
        dataset_name=ctx.dataset_name,
        workdir=ctx.workdir,
        src_path=Path("dummy"),
        dst_path=ctx.dst_path,
        new_dst_path=Path("dummy"),
        desc_stats_out=ctx.rw_desc_stats_out,
        weight_path=ctx.rw_weight_path,
        InterpMethod=ctx.rw_dataset.InterpMethod,
        scrip_path=ctx.scrip_path,
        num_cells=num_cells,
        mesh_name=ctx.mesh_name,
        field_names=ctx.rw_dataset.field_names,
        x_center=ctx.rw_dataset.x_center,
        y_center=ctx.rw_dataset.y_center,
        x_dim=ctx.rw_dataset.x_dim,
        y_dim=ctx.rw_dataset.y_dim,
        x_corner=ctx.rw_dataset.x_corner,
        y_corner=ctx.rw_dataset.y_corner,
        x_corner_dim=ctx.rw_dataset.x_corner_dim,
        y_corner_dim=ctx.rw_dataset.y_corner_dim,
        level_in_name=ctx.rw_dataset.level_in_name,
        level_out_name=ctx.rw_dataset.level_out_name,
        level_out_size=ctx.rw_dataset.level_out_size,
        time_name=ctx.rw_dataset.time_name,
        time_size=ctx.rw_dataset.time_size,
    )

    if ctx.dataset_name == "RAVE":
        processor = None
        for date_to_process in dates_needed:
            _LOGGER.info(f"RAVE processing {date_to_process=}")
            src_paths = find_latest_src_file(
                ctx.input_dir, date_to_process, ctx.ebb_dcycle, ctx.dataset_name, max_lookback_hours=24
            )
            if not src_paths:
                _LOGGER.warn(f"No matching files found for {date_to_process} (even after lookback).")
                continue

            _LOGGER.info(f"Reading RAVE file: {src_paths=}")
            src_path = src_paths[0]
            new_dst_path = ctx.output_dir / (ctx.mesh_name + "-RAVE-" + date_to_process + ".nc")

            # --- OPTIMIZATION START ---
            if processor is None:
                _LOGGER.info("FIRST PASS: Full Initialization")
                # This pays the "expensive" cost of loading weights/grids, but only once.

                regrid_context.src_path = src_path
                regrid_context.new_dst_path = new_dst_path

                processor = ChemRegridProcessor(context=regrid_context)
                processor.initialize()
            else:
                _LOGGER.info("SUBSEQUENT PASSES: Hot Swap")
                # Just update the paths in the existing context.
                # The grids and regridder (weights) remain loaded in memory.
                processor.context.src_path = src_path
                processor.context.new_dst_path = new_dst_path
            # Run the regridding (Fast)
            processor.run()
            # --- OPTIMIZATION END ---
            # Only finalize after ALL files are done
        if processor:
            processor.finalize()

            _LOGGER.info("success")

    elif ctx.dataset_name == "NGFS":
        processor = ChemRegridProcessor(context=regrid_context)

        for date_to_process in dates_needed:
            # Construct the filename (Adjust the prefix 'ngfs_' if your files are named differently)
            # print("GAF debug: attempting to read: " + input_dir + "/NGFS_v0.31_" + date_to_process + "_0p01.nc")
            ngfs_paths = glob.glob(str(ctx.input_dir) + "/NGFS_v0.31_0p01_" + date_to_process + "0000.nc")

            if not ngfs_paths:
                print(f"ERROR: Missing NGFS file for {date_to_process}. Skipping.")
                exit(1)
                # TODO: perhaps add a helper similarly as I added for RAVE to search for the latest
                # available file in case that the current datetime does not exist
                continue

            ngfs_path = Path(ngfs_paths[0])
            new_dst_path = Path(str(ctx.output_dir) + "/" + ctx.mesh_name + "-NGFS-" + date_to_process + ".nc")
            print(f"GAF reading NGFS file: {ngfs_path}")

            # Update context paths for the current hour
            processor.context.src_path = ngfs_path
            processor.context.new_dst_path = new_dst_path

            # Execute the dynamic regridding for this specific hour's fires
            # Note that resolution is hard coded...
            processor.process_ngfs_file(ngfs_path, resolution=0.01)

        _LOGGER.info("NGFS success")

    elif ctx.dataset_name == "GOES":
        processor = None
        date_to_process = dates_needed[0]
        src_paths = find_latest_src_file(ctx.input_dir, date_to_process, -1, ctx.dataset_name, max_lookback_hours=2)
        files_to_cat = src_paths
        _LOGGER.info(f"will cat files: {files_to_cat=}")
        if COMM.rank == 0:
            with xr.open_mfdataset(files_to_cat, combine="nested", concat_dim="file") as ds:
                # 2. Calculate the nanmean across the new 'file' dimension
                # skipna=True (default) ensures it behaves like np.nanmean
                ds_averaged = ds["AOD"].mean(dim="file", skipna=True)
            # _LOGGER.debug(ds_averaged)
            ds_averaged.encoding.update({"dtype": "float32", "_FillValue": -999})
            ds_averaged.to_netcdf(ctx.output_dir / "test_goes_aod_merged.nc")

        if not src_paths:
            msg = f"No matching GOES files found for {date_to_process} (even after lookback)."
            _LOGGER.error(msg)
            raise ValueError(msg)

        _LOGGER.info("Reading merged GOES file: test_goes_aod_merged.nc")
        # src_path = src_paths[0]
        src_path = ctx.output_dir / "test_goes_aod_merged.nc"
        new_dst_path = ctx.output_dir / (ctx.mesh_name + "-GOES-" + date_to_process + ".nc")
        # --- OPTIMIZATION START ---
        if processor is None:
            # FIRST PASS: Full Initialization
            # This pays the "expensive" cost of loading weights/grids, but only once.

            regrid_context.src_path = src_path
            regrid_context.new_dst_path = new_dst_path

            processor = ChemRegridProcessor(context=regrid_context)
            processor.initialize()
        else:
            # SUBSEQUENT PASSES: Hot Swap
            # Just update the paths in the existing context.
            # The grids and regridder (weights) remain loaded in memory.
            processor.context.src_path = src_path
            processor.context.new_dst_path = new_dst_path
        # Run the regridding (Fast)
        processor.run()
        # --- OPTIMIZATION END ---
        # Only finalize after ALL files are done
        if processor:
            processor.finalize()

        _LOGGER.info("success")

    elif ctx.dataset_name == "FMC":
        for date_to_process in dates_needed:
            src_paths = glob.glob(str(ctx.input_dir / ("fmc_" + date_to_process + ".nc")))
            src_path = Path(src_paths[0])
            new_dst_path = ctx.output_dir / ("fmc_" + date_to_process + "_" + ctx.mesh_name + ".nc")

            regrid_context.src_path = src_path
            regrid_context.new_dst_path = new_dst_path

            processor = ChemRegridProcessor(context=regrid_context)
            processor.initialize()
            processor.run()
            processor.finalize()

            _LOGGER.info("success")
    #
    elif ctx.dataset_name == "GRA2PES":
        src_path = ctx.input_dir / ("GRA2PESv1.0_total_2021" + MM + "_" + DOWs + "_00to11Z.nc")
        new_dst_path = ctx.output_dir / (ctx.dataset_name + "v1.0_total_" + ctx.mesh_name + "_00to11Z.nc")

        regrid_context.src_path = src_path
        regrid_context.new_dst_path = new_dst_path

        processor = ChemRegridProcessor(context=regrid_context)
        processor.initialize()
        processor.run()
        processor.finalize()

        _LOGGER.info("success")

        src_path = ctx.input_dir / ("GRA2PESv1.0_total_2021" + MM + "_" + DOWs + "_12to23Z.nc")
        new_dst_path = ctx.output_dir / (ctx.dataset_name + "v1.0_total_" + ctx.mesh_name + "_12to23Z.nc")

        regrid_context.src_path = src_path
        regrid_context.new_dst_path = new_dst_path

        processor = ChemRegridProcessor(context=regrid_context)
        processor.initialize()
        processor.run()
        processor.finalize()

        _LOGGER.info("success")

    else:
        if ctx.dataset_name == "PECM":
            src_path = ctx.input_dir / ("pollen_obs_" + YYYY + "_BELD6_ef_T_" + JJJ + ".nc")
            new_dst_path = ctx.output_dir / ("pollen_ef_" + ctx.mesh_name + "_" + YYYY + "_" + JJJ + ".nc")
        elif ctx.dataset_name == "NEMO_RWC":
            src_path = ctx.input_dir / "NEMO_RWC_POC_PEC_PMOTHR.annual.2017.nc"
            new_dst_path = ctx.output_dir / ("NEMO_RWC_ANNUAL_TOTAL_" + ctx.mesh_name + ".nc")
        elif ctx.dataset_name == "NEMO_ANTHRO":
            src_path = ctx.input_dir / ("NEMO_ANTHRO_" + ctx.mesh_name + "_" + YYYY + MM + DD + HH + "_SECTORSUM.nc")
            new_dst_path = ctx.output_dir / ("NEMO_ANTHRO_" + ctx.mesh_name + ".nc")
        elif ctx.dataset_name == "NARR":
            src_path = ctx.input_dir / "rwc_emission_denominator.2017.nc"
            new_dst_path = ctx.output_dir / ("NEMO_RWC_DENOMINATOR_2017_" + ctx.mesh_name + ".nc")
        elif ctx.dataset_name == "ECOREGION":
            src_path = ctx.input_dir / "veg_map.nc"
            new_dst_path = ctx.output_dir / ("ecoregions_" + ctx.mesh_name + "_mpas.nc")
        elif ctx.dataset_name == "FENGSHA_2D":
            src_path = ctx.input_dir / "FENGSHA_RRFS_NA_3km_2026_2D.nc"
            new_dst_path = ctx.output_dir / ("fengsha_dust_inputs.2D." + ctx.mesh_name + ".nc")
        elif ctx.dataset_name == "FENGSHA_2D_Time":
            src_path = ctx.input_dir / "FENGSHA_RRFS_NA_3km_2026_2D_Time.nc"
            new_dst_path = ctx.output_dir / ("fengsha_dust_inputs.2D_Time." + ctx.mesh_name + ".nc")

        regrid_context.src_path = src_path
        regrid_context.new_dst_path = new_dst_path

        processor = ChemRegridProcessor(context=regrid_context)
        processor.initialize()
        processor.run()
        processor.finalize()

        _LOGGER.info("success")
