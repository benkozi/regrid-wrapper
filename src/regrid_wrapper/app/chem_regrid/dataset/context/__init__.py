from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    DatasetName,
)
from regrid_wrapper.app.chem_regrid.dataset.context.ecoregion import (
    ECOREGION_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.fengsha_2d import (
    FENGSHA_2D_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.fengsha_2d_time import (
    FENGSHA_2D_Time_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.fmc import FMC_DatasetRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context.goes import GOES_DatasetRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context.gra2pes import (
    GRA2PES_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.narr import NARR_DatasetRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context.nemo_anthro import (
    NEMO_ANTHRO_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.nemo_rwc import (
    NEMO_RWC_DatasetRegridContext,
)
from regrid_wrapper.app.chem_regrid.dataset.context.ngfs import NGFS_DatasetRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context.pecm import PECM_DatasetRegridContext
from regrid_wrapper.app.chem_regrid.dataset.context.rave import RAVE_DatasetRegridContext


def get_regrid_context_class(name: DatasetName) -> type[AbstractDatasetRegridContext]:
    """Factory function to return the appropriate context class for a given dataset name."""
    klasses = {
        DatasetName.RAVE: RAVE_DatasetRegridContext,
        DatasetName.GRA2PES: GRA2PES_DatasetRegridContext,
        DatasetName.FMC: FMC_DatasetRegridContext,
        DatasetName.NEMO_RWC: NEMO_RWC_DatasetRegridContext,
        DatasetName.NEMO_ANTHRO: NEMO_ANTHRO_DatasetRegridContext,
        DatasetName.PECM: PECM_DatasetRegridContext,
        DatasetName.NARR: NARR_DatasetRegridContext,
        DatasetName.ECOREGION: ECOREGION_DatasetRegridContext,
        DatasetName.FENGSHA_2D: FENGSHA_2D_DatasetRegridContext,
        DatasetName.FENGSHA_2D_Time: FENGSHA_2D_Time_DatasetRegridContext,
        DatasetName.GOES: GOES_DatasetRegridContext,
        DatasetName.NGFS: NGFS_DatasetRegridContext,
    }
    return klasses[name]
