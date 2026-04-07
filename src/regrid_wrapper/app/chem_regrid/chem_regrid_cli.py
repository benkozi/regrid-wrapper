import argparse
from pathlib import Path
from typing import Any

import yaml

from regrid_wrapper.app.chem_regrid.chem_regrid_impl import main
from regrid_wrapper.app.chem_regrid.context import ChemRegridContext
from regrid_wrapper.app.override import apply_overrides


def chem_regrid_cli(args: argparse.Namespace) -> None:
    if args.yaml_path is not None:
        yaml_path = Path(args.yaml_path)
        yaml_data = yaml.safe_load(yaml_path.read_text())
        config = yaml_data[args.root_key]
    else:
        config = {}

    overrides = args.overrides
    if overrides:
        apply_overrides(overrides, config)

    ctx = ChemRegridContext.from_yaml(config)
    main(ctx)


def add_chem_regrid_parser(subparsers: Any) -> None:
    # chem_regrid sub-command
    parser_chem_regrid = subparsers.add_parser("chem-regrid", help="Run chem-regrid")
    parser_chem_regrid.add_argument(
        "--yaml-path", type=str, required=False, help="If provided, path to YAML file containing the configuration's root key"
    )
    parser_chem_regrid.add_argument(
        "--root-key", type=str, default="rw-chem-regrid", help="If provided, use this key when extracting the root configuration"
    )
    parser_chem_regrid.add_argument(
        "--overrides", nargs="+", help="If provided, override arbitrary key+values (e.g. --override key1:nest=val1 key2=val2)"
    )
