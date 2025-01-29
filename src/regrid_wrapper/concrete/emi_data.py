from copy import copy
from pathlib import Path
from typing import Tuple

import esmpy
import numpy as np

from pydantic import BaseModel, ConfigDict

from regrid_wrapper.concrete.rrfs_dust_data import RRFS_DUST_DATA_ENV
from regrid_wrapper.esmpy.field_wrapper import (
    NcToGrid,
    GridSpec,
    NcToField,
    resize_nc,
    GridWrapper,
    FieldWrapper,
)
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class EmiDataEnv(BaseModel):
    model_config = ConfigDict(frozen=True)
    fields: Tuple[str, ...] = ("e_bc", "e_oc", "e_pm25")
    dim_time: str = "time"


EMI_DATA_ENV = EmiDataEnv()


class EmiData(AbstractRegridOperation):

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileAndRegridFields)

        src_gwrap = self._create_source_grid_wrapper_()
        dst_gwrap = self._create_destination_grid_wrapper_()

        archetype_field_name = EMI_DATA_ENV.fields[0]
        src_fwrap = self._create_field_wrapper_(
            archetype_field_name, self._spec.src_path, src_gwrap
        )

        new_sizes = {
            EMI_DATA_ENV.dim_time: src_fwrap.dims.get(EMI_DATA_ENV.dim_time).size
        }
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
        for src_dim, dst_dim in zip(src_gwrap.dims.value, dst_gwrap_output.dims.value):
            dst_dim.name = src_dim.name
        dst_gwrap_output.fill_nc_variables(self._spec.output_filename)

        dst_fwrap = self._create_field_wrapper_(
            archetype_field_name, self._spec.output_filename, dst_gwrap_output
        )

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.BILINEAR
        regridder = esmpy.Regrid(
            src_fwrap.value,
            dst_fwrap.value,
            regrid_method=regrid_method,
            # filename=str(self._spec.output_weight_filename), # Disable since weight files differ per-variable
            unmapped_action=esmpy.UnmappedAction.IGNORE,
        )

        for field_to_regrid in EMI_DATA_ENV.fields:
            self._logger.info(f"regridding field: {field_to_regrid}")
            src_fwrap_regrid = self._create_field_wrapper_(
                field_to_regrid, self._spec.src_path, src_gwrap
            )
            dst_fwrap_regrid = self._create_field_wrapper_(
                field_to_regrid, self._spec.output_filename, dst_gwrap_output
            )

            regridder(
                src_fwrap_regrid.value,
                dst_fwrap_regrid.value,
            )

            dst_fwrap_regrid.fill_nc_variable(self._spec.output_filename)

    @staticmethod
    def _create_field_wrapper_(
        field_name: str, path: Path, gwrap: GridWrapper
    ) -> FieldWrapper:
        nc2field = NcToField(
            path=path,
            name=field_name,
            dim_time=(RRFS_DUST_DATA_ENV.dim_time,),
            gwrap=gwrap,
        )
        fwrap = nc2field.create_field_wrapper()
        return fwrap

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

    def _create_source_grid_wrapper_(self) -> GridWrapper:
        src_grid_def = NcToGrid(
            path=self._spec.src_path,
            spec=GridSpec(
                x_center="grid_lont",
                y_center="grid_latt",
                x_dim=("grid_xt",),
                y_dim=("grid_yt",),
            ),
        )
        src_gwrap = src_grid_def.create_grid_wrapper()
        return src_gwrap
