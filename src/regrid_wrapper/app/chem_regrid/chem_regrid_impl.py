# mypy: ignore-errors

import glob
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

import esmpy
import numpy as np
import pandas as pd
from pydantic import BaseModel

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.chem_regrid_context import ChemRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context import get_regrid_context_class
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    InterpMethod,
)
from regrid_wrapper.app.chem_regrid.dataset.src_field import SrcField
from regrid_wrapper.context.comm import COMM, reconcile_bounds
from regrid_wrapper.esmpy.field_wrapper import (
    FieldWrapper,
    GridSpec,
    GridWrapper,
    NcToField,
    NcToGrid,
    copy_nc_variable,
    open_nc,
    set_variable_data,
    HasNcAttrsType,
    copy_nc_variable, load_variable_data, MeshWrapper,
)


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


class FileDesc(BaseModel):
    path: Path
    origin: Literal["src", "dst"]
    field_names: tuple[str, ...]


class ChemRegridProcessor:
    _dst_mesh: esmpy.Mesh | None = None

    def __init__(self, context: AbstractDatasetRegridContext) -> None:
        self.context = context

        self._regridder: esmpy.Regrid | None = None
        self._dst_field: FieldWrapper | None = None
        self._src_gwrap: GridWrapper | None = None

    def initialize(self) -> None:
        CR_LOGGER.info(f"initialize: {self.context=}")
        esmpy.Manager(debug=True)

        pathsrc = self.context.get_src_grid_path()

        CR_LOGGER.info("create source grid")
        self._src_gwrap = NcToGrid(
            path=pathsrc,
            spec=GridSpec.model_validate(self.context.model_dump()),
        ).create_grid_wrapper()

        CR_LOGGER.info("create source field")
        src_fwrap = self.create_src_field_wrapper(self.context.src_fields[0].name)

        if self._dst_mesh is None:
            CR_LOGGER.info("create destination mesh")
            # dst_mesh = esmpy.Mesh(
            #     filename=str(self.context.input_mesh_path), filetype=esmpy.FileFormat.SCRIP
            # )
            self._dst_mesh = esmpy.Mesh(
                filename=str(self.context.input_mesh_path), filetype=esmpy.FileFormat.UGRID, meshname="grid_topology"
            )
        dst_mesh = self._dst_mesh
        local_bounds = reconcile_bounds((0, self._dst_mesh.size_owned[1]))

        self._dst_field = self._create_dst_field_(dst_mesh)
        self._regridder = self._create_regridder_(src_fwrap)

    def _create_dst_field_(self, dst_mesh: esmpy.Mesh) -> esmpy.Field:
        CR_LOGGER.info("create destination field")

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
        CR_LOGGER.info("create regridder")
        if self.context.weight_path.exists():
            CR_LOGGER.info("create regridder from file")
            regridder = esmpy.RegridFromFile(
                srcfield=src_fwrap.value,
                dstfield=self._dst_field.value,
                filename=str(self.context.weight_path),
            )
        else:
            CR_LOGGER.info("create regridder in-memory")
            method_map = {
                InterpMethod.CONSERVE: esmpy.RegridMethod.CONSERVE,
                InterpMethod.CONSERVE_2ND: esmpy.RegridMethod.CONSERVE_2ND,
                InterpMethod.BILINEAR: esmpy.RegridMethod.BILINEAR,
                InterpMethod.NEAREST_STOD: esmpy.RegridMethod.NEAREST_STOD,
            }
            # Default to NEAREST_STOD if not found in map (preserving original behavior)
            regrid_method = method_map[self.context.InterpMethod]

            CR_LOGGER.info(f"using {regrid_method} interp")
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
        CR_LOGGER.info("apply regridding")

        CR_LOGGER.info("create output file")
        self.create_output_file()

        for src_field in self.context.src_fields:
            self._regrid_src_field(src_field)

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

    def _regrid_src_field(self, src_field: SrcField) -> None:
        CR_LOGGER.info(f"regridding {src_field.name=}")
        regridder = self.get_regridder()
        src_fwrap = self.create_src_field_wrapper(field_name=src_field.name)

        dst_field = self.get_dst_field()
        dst_field.data.fill(0.0)
        regridder(src_fwrap.value, dst_field)

        local_bounds = (dst_field.lower_bounds[0], dst_field.upper_bounds[0])
        reconciled_bounds = reconcile_bounds(local_bounds)
        dims = src_field.create_dimension_collection(reconciled_bounds)
        CR_LOGGER.debug(f"{dims=}")
        CR_LOGGER.info("writing field to netcdf")
        with open_nc(self.context.new_dst_path, mode="a") as ds:
            transformed_data = self.context.transform_regridded_data(src_field, dst_field.data, ds, reconciled_bounds, dims)

            CR_LOGGER.info(f"creating variable {src_field.name=}")
            var = ds.createVariable(
                src_field.name,
                src_field.dtype,
                [dim.name[0] for dim in dims.value],
                fill_value=src_field.fill_value,
            )
            for k, v in src_field.attrs.items():
                setattr(var, k, v)

            CR_LOGGER.info(f"setting variable data {src_field.name=}")
            set_variable_data(
                var,
                dims,
                src_field.reshape_field_data(transformed_data),
                collective=True,
            )
        CR_LOGGER.info(f"finished writing field to netcdf {src_field.name=}")
        src_fwrap.value.destroy()
        del src_fwrap

        self.context.post_regrid_processing(src_field, regridder, self, dims)

    def create_output_file(self):
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
                        CR_LOGGER.debug("Not creating a time dimension")
                dst_nc.setncattr("created_at", str(datetime.now(timezone.utc)))
                dst_nc.setncattr("src_path", str(self.context.src_path))
                dst_nc.setncattr("dst_path", str(self.context.dst_path))

                with open_nc(self.context.dst_path, mode="r", parallel=False) as src_nc:
                    for varname in self.context.var_names_to_copy_to_output_file:
                        copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)

    def finalize(self) -> None:
        CR_LOGGER.info("finalizing")
        self._regridder.destroy()
        self._dst_field.value.destroy()
        self._src_gwrap.value.destroy()
        # TODO: There could be an option to destroy the destination mesh when finalizing. However,
        #  it is more efficient to leave it since the destination is not variable at this point.
        # self._dst_mesh.destroy()

    def create_desc_stuff(self, targets: Iterable[FileDesc]) -> pd.DataFrame:
        CR_LOGGER.info("entering create_desc_stuff")
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
        CR_LOGGER.info("exiting create_desc_stuff")
        return ret

    def create_src_field_wrapper(self, field_name: str) -> FieldWrapper:
        CR_LOGGER.info("create source field")
        src_fwrap = self._create_raw_src_field_wrapper_(field_name)
        self.context.update_src_field_wrapper(src_fwrap)
        return src_fwrap

    def _create_raw_src_field_wrapper_(self, field_name: str) -> FieldWrapper:
        dim_level, dim_time = self.context.get_src_field_dims(field_name)

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

    def get_dst_field(self) -> FieldWrapper:
        if self._dst_field is None:
            raise ValueError
        return self._dst_field

    def get_regridder(self) -> esmpy.Regrid:
        if self._regridder is None:
            raise ValueError
        return self._regridder

    def init_destination_only(self) -> None:
        """Loads the heavy MPAS destination mesh once for dynamic NGFS processing."""
        CR_LOGGER.info("Initializing MPAS Destination Mesh (Once)")
        esmpy.Manager(debug=True)

        # if not self.context.input_mesh_path.exists() and self.context.rank == 0:
        #     CR_LOGGER.info("writing mpas scrip grid")
        #     mpas_desc = MpasCellMeshDescriptor(
        #         str(self.context.dst_path), self.context.mesh_name + ".init"
        #     )
        #     mpas_desc.to_scrip(str(self.context.input_mesh_path))

        CR_LOGGER.info("create destination mesh")
        dst_mesh = esmpy.Mesh(filename=str(self.context.input_mesh_path), filetype=esmpy.FileFormat.UGRID, meshname="grid_topology")

        # Create destination field (using logic from your original initialize method)
        ndbounds = None
        if self.context.level_out_size > 1 and self.context.time_size > 1:
            ndbounds = (self.context.level_out_size, self.context.time_size)
        elif self.context.level_out_size > 1 and self.context.time_size == 1:
            ndbounds = (self.context.level_out_size,)
        elif self.context.level_out_size == 1 and self.context.time_size > 1:
            ndbounds = (self.context.time_size,)

        self._dst_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, ndbounds=ndbounds)

    def process_ngfs_file(self, file_path: Path, resolution: float = 0.01) -> None:
        """Dynamically builds a mesh for NGFS points, regrids, and writes the output."""
        CR_LOGGER.info(f"Processing NGFS file: {file_path}")

        # 1. Read NGFS Coordinates AND Area
        with open_nc(file_path, mode="r") as ds:
            lats = ds.variables["lat"][:].filled(np.nan)
            lons = ds.variables["lon"][:].filled(np.nan)

            # Read the NGFS area (in km2)
            if "GRID_AREA" in ds.variables:
                grid_area = ds.variables["GRID_AREA"][:].filled(np.nan)
            else:
                CR_LOGGER.warning("GRID_AREA not found! Defaulting to 1.0 km2.")
                grid_area = np.ones_like(lats)

        # Filter out NaNs
        valid = ~np.isnan(lats) & ~np.isnan(lons) & ~np.isnan(grid_area)
        lats = lats[valid]
        lons = lons[valid]
        grid_area = grid_area[valid]

        # CRITICAL FIX: Convert -180/180 to 0/360 to match MPAS grid
        lons = lons % 360.0

        if len(lats) == 0:
            CR_LOGGER.warning("No valid fires in file.")
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
            CR_LOGGER.info(f"regridding NGFS {src_field.name=}")

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
                    CR_LOGGER.warning(f"Variable {ngfs_var_name} not found! Skipping.")
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


def run_regridding(ctx: AbstractDatasetRegridContext) -> None:
    processor = None
    for file_pair in ctx.iter_file_pairs():
        # --- OPTIMIZATION START ---
        if processor is None:
            CR_LOGGER.info("FIRST PASS: Full Initialization")
            # This pays the "expensive" cost of loading weights/grids, but only once.
            ctx.src_path = file_pair.src_path
            ctx.new_dst_path = file_pair.dst_path

            processor = ChemRegridProcessor(context=ctx)
            processor.initialize()
        else:
            CR_LOGGER.info("SUBSEQUENT PASSES: Hot Swap")
            # Just update the paths in the existing context.
            # The grids and regridder (weights) remain loaded in memory.
            processor.context.src_path = file_pair.src_path
            processor.context.new_dst_path = file_pair.dst_path
        # Run the regridding (Fast)
        processor.run()
        # --- OPTIMIZATION END ---
        # Only finalize after ALL files are done
    if processor:
        processor.finalize()
    CR_LOGGER.info("success")


def main(ctx: ChemRegridContext) -> None:

    klass = get_regrid_context_class(ctx.dataset_name)
    regrid_context = klass(
        dataset_name=ctx.dataset_name,
        workdir=ctx.workdir,
        src_path=Path("dummy"),
        dst_path=ctx.rw_dst_path,
        new_dst_path=Path("dummy"),
        desc_stats_out=ctx.rw_desc_stats_out,
        weight_path=ctx.rw_weight_path,
        InterpMethod=ctx.rw_dataset.InterpMethod,
        input_mesh_path=ctx.rw_input_mesh_path,
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
        cycle=ctx.cycle,
        ebb_dcycle=ctx.ebb_dcycle,
        input_dir=ctx.input_dir,
        output_dir=ctx.output_dir,
    )

    if ctx.dataset_name == "NGFS":
        processor = ChemRegridProcessor(context=regrid_context)

        for date_to_process in regrid_context.dates_needed:
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

        CR_LOGGER.info("NGFS success")
    else:
        run_regridding(regrid_context)
