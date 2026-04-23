from datetime import timedelta
from functools import cached_property
from typing import Iterator

import esmpy
import numpy as np

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.context.comm import COMM


def create_ngfs_sparse_mesh(lat_1d: np.ndarray, lon_1d: np.ndarray, resolution: float = 0.01) -> esmpy.Mesh:
    """
    Creates an esmpy.Mesh dynamically from 1-D point source data.
    Calculates the 4 corners of a square cell of size `resolution`
    around each center point in memory.
    This is the best approach since NGFS data are point-source (1-D),
    but we rarely have more than 1000 fires in the domain, so we
    can afford to keep this in memory instead of creating a file.
    """

    num_cells = len(lat_1d)
    if num_cells == 0:
        raise ValueError("must have at least one cell in the mesh")

    num_nodes = num_cells * 4
    d = resolution / 2.0

    node_lons = np.column_stack([lon_1d - d, lon_1d + d, lon_1d + d, lon_1d - d]).flatten()

    node_lats = np.column_stack([lat_1d - d, lat_1d - d, lat_1d + d, lat_1d + d]).flatten()

    node_coords = np.empty(num_nodes * 2, dtype=np.float64)
    node_coords[0::2] = node_lons
    node_coords[1::2] = node_lats

    node_ids = np.arange(1, num_nodes + 1, dtype=np.int32)
    node_owners = np.full(num_nodes, COMM.rank, dtype=np.int32)

    element_ids = np.arange(1, num_cells + 1, dtype=np.int32)
    element_types = np.full(num_cells, esmpy.MeshElemType.QUAD, dtype=np.int32)

    # CRITICAL FIX: esmpy expects 0-based indexing for connectivity!
    element_conn = np.arange(0, num_nodes, dtype=np.int32)

    # Explicitly set spherical coordinates
    mesh = esmpy.Mesh(parametric_dim=2, spatial_dim=2, coord_sys=esmpy.CoordSys.SPH_DEG)

    mesh.add_nodes(node_count=num_nodes, node_ids=node_ids, node_coords=node_coords, node_owners=node_owners)

    mesh.add_elements(element_count=num_cells, element_ids=element_ids, element_types=element_types, element_conn=element_conn)

    return mesh


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
