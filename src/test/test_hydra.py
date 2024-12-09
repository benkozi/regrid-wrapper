from hydra import initialize, compose

# tdk: remove hydra? if so, put this snippet somewhere

# def test_basic_conf_loading() -> None:
#     with initialize(config_path="bin/conf"):
#         cfg = compose(config_name="regrid-op")
#         op = RegridOperation(**cfg.regrid)
#     assert isinstance(op, RegridOperation)
