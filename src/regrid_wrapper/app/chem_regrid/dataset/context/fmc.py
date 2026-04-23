from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Iterator

from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)


class FMC_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for FMC (Fuel Moisture Content) data."""

    def _get_src_search_path(self, this_time: datetime) -> str:
        this_str = this_time.strftime(self.search_time_format)
        return str(self.input_dir / ("fmc_" + this_str + ".nc"))

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for date_to_process in self.dates_needed:
            src_paths = self.find_latest_src_file(date_to_process)
            src_path = Path(src_paths[0])
            new_dst_path = self.output_dir / ("fmc_" + date_to_process + "_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        for i in range(25):
            x = self.dt_spec.datetime - timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed
