from pathlib import Path

import pytest

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.logging import init_logging
from test.conftest import custom_env


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
