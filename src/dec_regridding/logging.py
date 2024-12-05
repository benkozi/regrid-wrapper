import logging
import logging.config

DEFAULT_LEVEL = logging.DEBUG
PROJECT_NAME = "declarative-regridding"
LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "plain": {
            "format": "[%(name)s][%(levelname)s][%(asctime)s][%(pathname)s:%(lineno)d][%(process)d][%(thread)d]: %(message)s"
        },
    },
    "handlers": {
        "default": {
            "formatter": "plain",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": [],
        },
    },
    "loggers": {
        PROJECT_NAME: {
            "handlers": ["default"],
            "level": DEFAULT_LEVEL,
        },
    },
}


def init_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)


init_logging()
LOGGER = logging.getLogger(PROJECT_NAME)
