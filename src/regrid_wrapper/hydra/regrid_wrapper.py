import hydra
from omegaconf import DictConfig, OmegaConf


@hydra.main(
    version_base=None, config_path="conf/smoke-dust", config_name="smoke-dust-config"
)
def regrid_wrapper_app(cfg: DictConfig) -> None:
    print(OmegaConf.to_yaml(cfg))


if __name__ == "__main__":
    regrid_wrapper_app()
