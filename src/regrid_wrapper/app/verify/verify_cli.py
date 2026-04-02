import argparse
from pathlib import Path
from typing import Any

import yaml

from regrid_wrapper.app.verify.context import VerifyContext
from regrid_wrapper.app.verify.runner import run_verify


def verify_cli(args: argparse.Namespace) -> None:
    yaml_path = Path(args.yaml_path)
    root_key = args.root_key
    yaml_data = yaml.safe_load(yaml_path.read_text())
    ctx = VerifyContext(**yaml_data[root_key])
    run_verify(ctx)


def add_verify_parser(subparsers: Any) -> None:
    # verify sub-command
    parser_verify = subparsers.add_parser("verify", help="Verify data files using nccmp.")
    parser_verify.add_argument(
        "--yaml-path", type=str, required=True, help="Path to YAML file containing the configuration's root key"
    )
    parser_verify.add_argument(
        "--root-key", type=str, default="rw-verify", help="If provided, use this key when extracting the root configuration"
    )
