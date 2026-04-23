from typing import Iterator

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)


class FENGSHA_2D_Time_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for FENGSHA 2D dust emission data with time dimension."""

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "FENGSHA_RRFS_NA_3km_2026_2D_Time.nc"
            new_dst_path = self.output_dir / ("fengsha_dust_inputs.2D_Time." + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)
