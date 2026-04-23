from regrid_wrapper.app.chem_regrid.dataset.context.base import AbstractDatasetRegridContext, DatasetName


def get_regrid_context_class(name: DatasetName) -> type["AbstractDatasetRegridContext"]:
    """Factory function to return the appropriate context class for a given dataset name."""
    if name == DatasetName.RAVE:
        from regrid_wrapper.app.chem_regrid.dataset.context.rave import (
            RAVE_DatasetRegridContext,
        )

        return RAVE_DatasetRegridContext
    elif name == DatasetName.GRA2PES:
        from regrid_wrapper.app.chem_regrid.dataset.context.gra2pes import (
            GRA2PES_DatasetRegridContext,
        )

        return GRA2PES_DatasetRegridContext
    elif name == DatasetName.FMC:
        from regrid_wrapper.app.chem_regrid.dataset.context.fmc import (
            FMC_DatasetRegridContext,
        )

        return FMC_DatasetRegridContext
    elif name == DatasetName.NEMO_RWC:
        from regrid_wrapper.app.chem_regrid.dataset.context.nemo_rwc import (
            NEMO_RWC_DatasetRegridContext,
        )

        return NEMO_RWC_DatasetRegridContext
    elif name == DatasetName.NEMO_ANTHRO:
        from regrid_wrapper.app.chem_regrid.dataset.context.nemo_anthro import (
            NEMO_ANTHRO_DatasetRegridContext,
        )

        return NEMO_ANTHRO_DatasetRegridContext
    elif name == DatasetName.PECM:
        from regrid_wrapper.app.chem_regrid.dataset.context.pecm import (
            PECM_DatasetRegridContext,
        )

        return PECM_DatasetRegridContext
    elif name == DatasetName.NARR:
        from regrid_wrapper.app.chem_regrid.dataset.context.narr import (
            NARR_DatasetRegridContext,
        )

        return NARR_DatasetRegridContext
    elif name == DatasetName.ECOREGION:
        from regrid_wrapper.app.chem_regrid.dataset.context.ecoregion import (
            ECOREGION_DatasetRegridContext,
        )

        return ECOREGION_DatasetRegridContext
    elif name == DatasetName.FENGSHA_2D:
        from regrid_wrapper.app.chem_regrid.dataset.context.fengsha_2d import (
            FENGSHA_2D_DatasetRegridContext,
        )

        return FENGSHA_2D_DatasetRegridContext
    elif name == DatasetName.FENGSHA_2D_Time:
        from regrid_wrapper.app.chem_regrid.dataset.context.fengsha_2d_time import (
            FENGSHA_2D_Time_DatasetRegridContext,
        )

        return FENGSHA_2D_Time_DatasetRegridContext
    elif name == DatasetName.GOES:
        from regrid_wrapper.app.chem_regrid.dataset.context.goes import (
            GOES_DatasetRegridContext,
        )

        return GOES_DatasetRegridContext
    elif name == DatasetName.NGFS:
        from regrid_wrapper.app.chem_regrid.dataset.context.ngfs import (
            NGFS_DatasetRegridContext,
        )

        return NGFS_DatasetRegridContext
    else:
        raise ValueError(f"Unknown dataset name: {name}")
