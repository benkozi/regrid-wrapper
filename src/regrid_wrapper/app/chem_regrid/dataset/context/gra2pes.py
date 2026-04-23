from typing import Iterator

import numpy as np

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.esmpy.field_wrapper import FieldWrapper


class GRA2PES_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for GRA2PES (Great Lakes Regional Air Pollution Emissions System) data."""

    def get_src_field_dims(self, field_name: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
        dim_level, dim_time = super().get_src_field_dims(field_name)
        if field_name == "h_agl":
            dim_level = ("bottom_top_stag",)
        return dim_level, dim_time

    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        """Converts GRA2PES emissions from metric tons/km2/hr or moles/km2/hr to ug/m2/s."""
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.value.data

        # GRA2PES PM, convert from metric tons/km2/hr to ug/m2/s
        if field_name in ("PM25-PRI", "PM10-PRI"):
            conv_aer = 1.0e6 / 3600.0
        # GRA2PES methane, convert from moles/km2/hr to ug/m2/s
        elif field_name in ("HC01", "SO2", "CO", "NH3", "NOX"):
            conv_aer = 1.0e-6 / 3600.0
        else:
            conv_aer = 1.0

        src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        # Define the parts that change
        suffixes = ["00to11Z", "12to23Z"]

        # Common string components
        src_prefix = f"GRA2PESv1.0_total_2021{self.dt_spec.mm}_{self.dt_spec.dows}_"
        dst_prefix = f"{self.dataset_name}v1.0_total_{self.mesh_name}_"

        for suffix in suffixes:
            yield RegridFilePair(
                src_path=self.input_dir / f"{src_prefix}{suffix}.nc", dst_path=self.output_dir / f"{dst_prefix}{suffix}.nc"
            )
