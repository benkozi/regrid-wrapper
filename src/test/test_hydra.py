from hydra import initialize, compose

from dec_regridding.model.regrid_operation import RegridOperation


def test_basic_conf_loading() -> None:
    with initialize(config_path="bin/conf"):
        cfg = compose(config_name="regrid-op")
        op = RegridOperation(**cfg.regrid)
    assert isinstance(op, RegridOperation)
