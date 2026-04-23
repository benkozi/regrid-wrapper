from typing import Iterator

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)


class ECOREGION_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for Ecoregion mapping data."""

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "veg_map.nc"
            new_dst_path = self.output_dir / ("ecoregions_" + self.mesh_name + "_mpas.nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)
