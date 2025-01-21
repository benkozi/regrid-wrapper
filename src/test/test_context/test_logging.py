import logging
from enum import StrEnum, unique
from pathlib import Path

import pytest

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.logging import init_logging
from test.conftest import custom_env, TEST_LOGGER


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


@unique
class ExitOnError(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"


EXIT_ON_ERROR = ExitOnError.TRUE


def do_log(
    msg,
    logger=TEST_LOGGER,
    level=logging.INFO,
    exc_info: Exception = None,
    stacklevel: int = 2,
):
    logger.log(level, msg, exc_info=exc_info, stacklevel=stacklevel)
    if exc_info is not None and EXIT_ON_ERROR == EXIT_ON_ERROR.TRUE:
        raise exc_info


def raise_error():
    do_log("in raise_error")
    x = {}
    _ = x["a"]


@pytest.mark.mpi
def test_file_and_line_number() -> None:
    do_log("hello world", level=logging.DEBUG)

    try:
        raise_error()
    except Exception as e:
        with pytest.raises(KeyError):
            do_log("big error", exc_info=e, level=logging.ERROR)
