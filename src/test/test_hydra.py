import glob
import subprocess
from pathlib import Path

import pytest

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.hydra.run_operations import do_run_operations
from regrid_wrapper.hydra.task_prep import do_task_prep
from regrid_wrapper.model.config import (
    SmokeDustRegridConfig,
    RrfsGridKey,
    Component,
    ComponentKey,
    SourceDefinition,
    RrfsGrid,
)
from test.conftest import (
    create_veg_map_file,
    create_rrfs_grid_file,
    create_dust_data_file,
)


def create_fake_cfg(tmp_path_shared: Path) -> SmokeDustRegridConfig:
    root_output_directory = tmp_path_shared / "root"
    veg_map_path = tmp_path_shared / "veg_map_source.nc"
    rrfs_grid_path = tmp_path_shared / "rrfs_grid_source.nc"
    dust_path = tmp_path_shared / "dust_source.nc"
    if COMM.rank == 0:
        _ = create_veg_map_file(veg_map_path, ["emiss_factor"])
        _ = create_rrfs_grid_file(rrfs_grid_path)
        _ = create_dust_data_file(dust_path)
    COMM.barrier()
    components = {
        ComponentKey.VEG_MAP: Component(grid=veg_map_path),
        ComponentKey.RAVE_GRID: Component(grid=rrfs_grid_path),
        ComponentKey.DUST: Component(grid=dust_path),
    }
    nodes = 2
    rrfs_grids = {
        RrfsGridKey.RRFS_CONUS_25KM: RrfsGrid(grid=rrfs_grid_path, nodes=nodes),
        RrfsGridKey.RRFS_CONUS_13KM: RrfsGrid(grid=rrfs_grid_path, nodes=nodes),
        RrfsGridKey.RRFS_NA_13KM: RrfsGrid(grid=rrfs_grid_path, nodes=nodes),
    }
    source_definition = SourceDefinition(components=components, rrfs_grids=rrfs_grids)
    cfg = SmokeDustRegridConfig(
        target_grids=[
            RrfsGridKey.RRFS_CONUS_25KM,
            RrfsGridKey.RRFS_NA_13KM,
            RrfsGridKey.RRFS_CONUS_13KM,
        ],
        target_components=[
            ComponentKey.VEG_MAP,
            ComponentKey.RAVE_GRID,
            ComponentKey.DUST,
        ],
        root_output_directory=root_output_directory,
        source_definition=source_definition,
    )
    return cfg


def test_do_task_prep(tmp_path_shared: Path) -> None:
    cfg = create_fake_cfg(tmp_path_shared)
    do_task_prep(cfg)
    stuff = glob.glob(str(tmp_path_shared / "**"), recursive=True)
    print(stuff)
    assert len(stuff) == 17


@pytest.mark.mpi
def test_run_operations(tmp_path_shared: Path) -> None:
    cfg = create_fake_cfg(tmp_path_shared)

    if COMM.rank == 0:
        do_task_prep(cfg)
    COMM.barrier()

    do_run_operations(cfg)
    COMM.barrier()

    globs = glob.glob(str(tmp_path_shared / "**"), recursive=True)
    # for g in globs:
    #     print(g)
    assert len(globs) == 32
