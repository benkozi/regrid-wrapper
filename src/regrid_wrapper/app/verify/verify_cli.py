import argparse
from pathlib import Path

import yaml

from regrid_wrapper.app.verify.context import VerifyContext
from regrid_wrapper.app.verify.runner import run_verify


def verify_cli(args: argparse.Namespace) -> None:
    yaml_path = Path(args.yaml_path)
    root_key = args.root_key
    yaml_data = yaml.safe_load(yaml_path.read_text())
    ctx = VerifyContext(**yaml_data[root_key])
    run_verify(ctx)
