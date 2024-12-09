from pathlib import Path

import pytest

from dec_regridding.context.comm import COMM
from dec_regridding.context.env import ENV
from dec_regridding.context.logging import init_logging
from test.conftest import TEST_LOGGER, custom_env


@pytest.mark.mpi
def test(tmp_path_shared: Path) -> None:
    with custom_env(**{"LOG_DIR": str(tmp_path_shared)}):
        logger = init_logging()
        logger.info("hello world")
        COMM.barrier()
        log_files = list(tmp_path_shared.glob("*"))
        logger.info(log_files)
        assert len(log_files) == COMM.size
    init_logging()
