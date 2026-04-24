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
from regrid_wrapper.app.chem_regrid.dataset.context.ngfs import run_ngfs_regridding
from regrid_wrapper.app.chem_regrid.dataset.src_field import SrcField
from regrid_wrapper.context.comm import reconcile_bounds
from regrid_wrapper.esmpy.field_wrapper import (
    Dimension,
    DimensionCollection,
    FieldWrapper,
    GridSpec,
    GridWrapper,
    MeshWrapper,
    NcToField,
    NcToGrid,
    open_nc,
    set_variable_data,
)


class FileDesc(BaseModel):
    path: Path
    origin: Literal["src", "dst"]
    field_names: tuple[str, ...]


class ChemRegridProcessor:
    _dst_mesh: esmpy.Mesh | None = None

    def __init__(self, context: AbstractDatasetRegridContext) -> None:
        self.context = context

        self._regridder: esmpy.Regrid | None = None
        self._dst_fwrap: FieldWrapper | None = None
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
            self._dst_mesh = esmpy.Mesh(
                filename=str(self.context.input_mesh_path), filetype=esmpy.FileFormat.UGRID, meshname="grid_topology"
            )
        dst_mesh = self._dst_mesh

        self._dst_fwrap = self._create_dst_fwrap_(dst_mesh)
        self._regridder = self._create_regridder_(src_fwrap)

    def _create_dst_fwrap_(self, dst_mesh: esmpy.Mesh) -> FieldWrapper:
        CR_LOGGER.info("create destination field")

        local_bounds = reconcile_bounds((0, self.get_dst_mesh().size_owned[1]))
        cells_dim = Dimension(
            name=("nCells",),
            size=self.context.num_cells,
            lower=local_bounds[0],
            upper=local_bounds[1],
            staggerloc=esmpy.MeshLoc.ELEMENT,
            coordinate_type="element",
        )
        dims = [cells_dim]
        ndbounds = []
        if self.context.level_out_size is not None and self.context.level_out_size > 0:
            if self.context.level_out_name is None:
                raise ValueError("level_out_name must be specified if level_out_size > 0")
            level_dim = Dimension(
                name=self.context.level_out_name,
                size=self.context.level_out_size,
                staggerloc=esmpy.StaggerLoc.CENTER,
                coordinate_type="level",
                lower=0,
                upper=self.context.level_out_size,
            )
            dims.append(level_dim)
            ndbounds.append(self.context.level_out_size)
        if self.context.time_size is not None and self.context.time_size > 0:
            ndbounds.append(self.context.time_size)
            time_dim = Dimension(
                name=("Time",),
                size=self.context.time_size,
                staggerloc=esmpy.StaggerLoc.CENTER,
                coordinate_type="time",
                lower=0,
                upper=self.context.time_size,
            )

            dims.append(time_dim)
        kwargs = {}
        if ndbounds:
            kwargs["ndbounds"] = tuple(ndbounds)

        esmpy_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT, **kwargs)
        gwrap = MeshWrapper(value=dst_mesh, dims=DimensionCollection(value=(cells_dim,)))
        return FieldWrapper(value=esmpy_field, gwrap=gwrap, dims=DimensionCollection(value=tuple(dims)))

    def _create_regridder_(self, src_fwrap: FieldWrapper) -> esmpy.RegridFromFile | esmpy.Regrid:
        CR_LOGGER.info("create regridder")
        if self.context.weight_path.exists():
            CR_LOGGER.info("create regridder from file")
            regridder = esmpy.RegridFromFile(
                srcfield=src_fwrap.value,
                dstfield=self.get_dst_fwrap().value,
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
            regrid_method = method_map[self.context.InterpMethod]

            CR_LOGGER.info(f"using {regrid_method} interp")
            regridder = esmpy.Regrid(
                srcfield=src_fwrap.value,
                dstfield=self.get_dst_fwrap().value,
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
        self.context.create_output_file()

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

        dst_fwrap = self.get_dst_fwrap()
        dst_fwrap.data.fill(0.0)
        regridder(src_fwrap.value, dst_fwrap.value)

        dims = src_field.create_dimension_collection(dst_fwrap.gwrap.dims.value[0].bounds)
        CR_LOGGER.debug(f"{dims=}")
        CR_LOGGER.info("writing field to netcdf")
        with open_nc(self.context.new_dst_path, mode="a") as ds:
            transformed_data = self.context.transform_regridded_data(src_field, dst_fwrap, ds, dims)

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
                dst_fwrap.dims,
                transformed_data,
                collective=True,
            )
        CR_LOGGER.info(f"finished writing field to netcdf {src_field.name=}")
        src_fwrap.value.destroy()
        del src_fwrap

        self.context.post_regrid_processing(src_field, regridder, self, dims)

    def finalize(self) -> None:
        CR_LOGGER.info("finalizing")
        self.get_regridder().destroy()
        self.get_dst_fwrap().value.destroy()
        self.get_src_gwrap().value.destroy()
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

    def get_dst_fwrap(self) -> FieldWrapper:
        if self._dst_fwrap is None:
            raise ValueError
        return self._dst_fwrap

    def get_regridder(self) -> esmpy.Regrid:
        if self._regridder is None:
            raise ValueError
        return self._regridder

    def get_dst_mesh(self) -> esmpy.Mesh:
        if self._dst_mesh is None:
            raise ValueError
        return self._dst_mesh


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
        run_ngfs_regridding(regrid_context)
    else:
        run_regridding(regrid_context)
