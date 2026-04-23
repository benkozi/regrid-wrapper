from typing import Any, Iterator, Union

import esmpy

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.app.chem_regrid.dataset.src_field import SrcField
from regrid_wrapper.esmpy.field_wrapper import (
    DimensionCollection,
    open_nc,
    set_variable_data,
)


class PECM_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for PECM (Pollen Emissions for Climate Models) data."""

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / ("pollen_obs_" + self.dt_spec.yyyy + "_BELD6_ef_T_" + self.dt_spec.jjj + ".nc")
            new_dst_path = self.output_dir / (
                "pollen_ef_" + self.mesh_name + "_" + self.dt_spec.yyyy + "_" + self.dt_spec.jjj + ".nc"
            )
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)

    def post_regrid_processing(
        self,
        src_field: SrcField,
        regridder: Union[esmpy.Regrid, esmpy.RegridFromFile],
        processor: Any,
        dims: DimensionCollection,
    ) -> None:
        if src_field.name == "ENL_POLL":
            with open_nc(self.new_dst_path, mode="a") as ds:
                CR_LOGGER.info("renaming and combining tree fields")

                src_fwrap_enl = processor.create_src_field_wrapper(field_name="ENL_POLL")
                dst_field_enl = processor.get_dst_field()
                dst_field_enl.data.fill(0.0)
                regridder(src_fwrap_enl.value, dst_field_enl)
                data_enl = src_field.reshape_field_data(dst_field_enl.data).copy()

                src_fwrap_dbl = processor.create_src_field_wrapper(field_name="DBL_POLL")
                dst_field_dbl = processor.get_dst_field()
                dst_field_dbl.data.fill(0.0)
                regridder(src_fwrap_dbl.value, dst_field_dbl)
                data_dbl = src_field.reshape_field_data(dst_field_dbl.data)

                var = ds.createVariable(
                    "TREE_POLL",
                    src_field.dtype,
                    [dim.name[0] for dim in dims.value],
                    fill_value=src_field.fill_value,
                )
                for k, v in src_field.attrs.items():
                    setattr(var, k, v)
                set_variable_data(
                    var,
                    dims,
                    data_enl + data_dbl,
                    collective=True,
                )
            src_fwrap_enl.value.destroy()
            src_fwrap_dbl.value.destroy()
