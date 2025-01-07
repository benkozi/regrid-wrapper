import hydra
from omegaconf import DictConfig

from regrid_wrapper.concrete.core import iter_operations
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.model.config import SmokeDustRegridConfig
from regrid_wrapper.strategy.core import RegridProcessor


def do_run_operations(cfg: SmokeDustRegridConfig) -> None:
    logger = LOGGER.getChild("run_operations")
    logger.info(cfg)
    for op in iter_operations(cfg):
        processor = RegridProcessor(op)
        processor.execute()
    logger.info("success")


@hydra.main(version_base=None, config_path="conf", config_name="smoke-dust-config")
def do_run_operations_cli(cfg: DictConfig) -> None:
    sd_cfg = SmokeDustRegridConfig.model_validate(cfg)
    do_run_operations_cli(sd_cfg)


if __name__ == "__main__":
    do_run_operations_cli()
