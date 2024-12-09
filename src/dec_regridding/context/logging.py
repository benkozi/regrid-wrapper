import logging
import logging.config

from dec_regridding.context.env import ENV
from dec_regridding.context.comm import COMM


def init_logging() -> logging.Logger:
    project_name = "declarative-regridding"
    logging_config: dict = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "plain": {
                "format": f"[%(name)s][%(levelname)s][%(asctime)s][%(pathname)s:%(lineno)d][%(process)d][%(thread)d][{COMM.rank}]: %(message)s"
            },
        },
        "handlers": {
            "default": {
                "formatter": "plain",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": [],
            },
            "file": {
                "formatter": "plain",
                "class": "logging.FileHandler",
                "filename": ENV.create_log_file_path(),
                "mode": "w",
            },
        },
        "loggers": {
            project_name: {
                "handlers": ["default", "file"],
                "level": ENV.LOG_LEVEL,
            },
        },
    }
    logging.config.dictConfig(logging_config)
    return logging.getLogger(project_name)


LOGGER = init_logging()
LOGGER.info(ENV)
