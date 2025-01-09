from pathlib import Path

import esmpy

from regrid_wrapper.esmpy.field_wrapper import NcToGrid, GridSpec, GridWrapper
from regrid_wrapper.model.spec import GenerateWeightFileSpec
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class RaveToRrfs(AbstractRegridOperation):

    @staticmethod
    def _create_grid_wrapper_(path: Path) -> GridWrapper:
        nc2grid = NcToGrid(
            path=path,
            spec=GridSpec(
                x_center="grid_lont",
                y_center="grid_latt",
                x_dim=("grid_xt",),
                y_dim=("grid_yt",),
                x_corner="grid_lon",
                y_corner="grid_lat",
                x_corner_dim=("grid_x",),
                y_corner_dim=("grid_y",),
            ),
        )
        gwrap = nc2grid.create_grid_wrapper()
        return gwrap

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileSpec)

        src_gwrap = self._create_grid_wrapper_(self._spec.src_path)
        dst_gwrap = self._create_grid_wrapper_(self._spec.dst_path)

        src_field = esmpy.Field(src_gwrap.value, name="src")
        dst_field = esmpy.Field(dst_gwrap.value, name="dst")

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.CONSERVE
        regridder = esmpy.Regrid(
            src_field,
            dst_field,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )

        _ = esmpy.RegridFromFile(
            src_field, dst_field, str(self._spec.output_weight_filename)
        )
