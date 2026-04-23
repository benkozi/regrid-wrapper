from typing import Iterator

import numpy as np

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.esmpy.field_wrapper import FieldWrapper


class NEMO_RWC_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for NEMO RWC (Residential Wood Combustion) data."""

    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        """Converts NEMO RWC emissions from g/s/km2 to ug/m2/s."""
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.value.data

        if field_name in ("PEC", "POC", "PMOTHR", "PMC"):
            # Convert g/s/km2 (on 1km grid) to ug/m2/s -->
            conv_aer = 1.0
        else:
            conv_aer = 1.0

        src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "NEMO_RWC_POC_PEC_PMOTHR.annual.2017.nc"
            new_dst_path = self.output_dir / ("NEMO_RWC_ANNUAL_TOTAL_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)
