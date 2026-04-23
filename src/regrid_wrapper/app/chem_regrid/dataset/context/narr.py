from typing import Iterator

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)


class NARR_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for NARR (North American Regional Reanalysis) data."""

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "rwc_emission_denominator.2017.nc"
            new_dst_path = self.output_dir / ("NEMO_RWC_DENOMINATOR_2017_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)
