from copy import copy
from pathlib import Path

import esmpy

from regrid_wrapper.esmpy.field_wrapper import (
    GridWrapper,
    NcToGrid,
    GridSpec,
    FieldWrapper,
    NcToField,
    resize_nc,
)
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class RrfsSmokeDustVegetationMap(AbstractRegridOperation):

    def _create_source_grid_wrapper_(self) -> GridWrapper:
        src_grid_def = NcToGrid(
            path=self._spec.src_path,
            spec=GridSpec(
                x_center="geolon",
                y_center="geolat",
                x_dim=("geolon", "lon"),
                y_dim=("geolat", "lat"),
            ),
        )
        src_gwrap = src_grid_def.create_grid_wrapper()
        return src_gwrap

    def _create_destination_grid_wrapper_(self):
        dst_grid_def = NcToGrid(
            path=self._spec.dst_path,
            spec=GridSpec(
                x_center="grid_lont",
                y_center="grid_latt",
                x_dim=("grid_xt",),
                y_dim=("grid_yt",),
            ),
        )
        dst_gwrap = dst_grid_def.create_grid_wrapper()
        return dst_gwrap

    @staticmethod
    def _create_field_wrapper_(
        field_name: str, path: Path, gwrap: GridWrapper
    ) -> FieldWrapper:
        nc2field = NcToField(
            path=path,
            name=field_name,
            gwrap=gwrap,
        )
        fwrap = nc2field.create_field_wrapper()
        return fwrap

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileAndRegridFields)

        field_to_regrid = "emiss_factor"

        src_gwrap = self._create_source_grid_wrapper_()
        dst_gwrap = self._create_destination_grid_wrapper_()

        src_fwrap = self._create_field_wrapper_(
            field_to_regrid, self._spec.src_path, src_gwrap
        )

        new_sizes = {}
        for axis in [
            (src_gwrap.spec.x_dim, dst_gwrap.spec.x_dim),
            (src_gwrap.spec.y_dim, dst_gwrap.spec.y_dim),
        ]:
            for dimname in axis[0]:
                new_sizes[dimname] = dst_gwrap.dims.get(axis[1]).size
        self._logger.info(f"resizing netcdf. new_sizes={new_sizes}")
        if self._spec.output_filename.exists():
            raise ValueError("output file must not exist")
        resize_nc(
            self._spec.src_path,
            self._spec.output_filename,
            new_sizes,
        )

        dst_gwrap_output = copy(dst_gwrap)
        dst_gwrap_output.spec = src_gwrap.spec
        dst_gwrap_output.dims = src_gwrap.dims
        dst_gwrap_output.fill_nc_variables(self._spec.output_filename)

        dst_fwrap = self._create_field_wrapper_(
            field_to_regrid, self._spec.output_filename, dst_gwrap_output
        )

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.BILINEAR
        regridder = esmpy.Regrid(
            src_fwrap.value,
            dst_fwrap.value,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.ERROR,
        )

        self._logger.info(f"regridding field: {field_to_regrid}")
        regridder(
            src_fwrap.value,
            dst_fwrap.value,
            zero_region=esmpy.Region.SELECT,
        )
        dst_fwrap.fill_nc_variable(self._spec.output_filename)
