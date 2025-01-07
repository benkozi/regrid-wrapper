import hydra
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig, OmegaConf

from regrid_wrapper.model.config import SmokeDustRegridConfig


@hydra.main(version_base=None, config_path="conf", config_name="smoke-dust-config")
def regrid_wrapper_app(cfg: DictConfig) -> None:
    # print(cfg.)
    # cfg = SmokeDustRegridConfig(**cfg)
    # cfg = SmokeDustRegridConfig.model_validate(cfg)
    # print(cfg)
    # return
    # dict_cfg = OmegaConf.to_container(cfg, resolve=True)
    #
    # import pdb
    #
    # pdb.set_trace()
    sd_cfg = SmokeDustRegridConfig.model_validate(cfg)
    print(sd_cfg)


if __name__ == "__main__":
    regrid_wrapper_app()
