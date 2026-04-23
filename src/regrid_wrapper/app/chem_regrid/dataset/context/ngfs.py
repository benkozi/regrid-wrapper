from datetime import timedelta
from functools import cached_property
from typing import Iterator

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)


class NGFS_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for NGFS (Next Generation Fire System) data."""

    def get_read_name(self, field_name: str) -> str:
        if field_name == "PM25":
            return "EMIS_PM25"
        return super().get_read_name(field_name)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        raise NotImplementedError("NGFS not yet supported")

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        # Determine the cycle dates to process +%Y%m%d%H
        # This is for RETROS (using current datetime, not day before)
        for i in range(25):  # GAF retro current day emissions
            if self.ebb_dcycle == 1:  # Same-day emissions
                x = self.dt_spec.datetime + timedelta(hours=i)
            elif self.ebb_dcycle == -1 or self.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = self.dt_spec.datetime - timedelta(hours=i)
            else:
                CR_LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = self.dt_spec.datetime + timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed
