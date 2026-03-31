import argparse
from pathlib import Path

import yaml

from regrid_wrapper.app.chem_regrid.context import ChemRegridContext
from regrid_wrapper.app.override import apply_overrides


def chem_regrid_cli(args: argparse.Namespace) -> None:
    yaml_path = Path(args.yaml_path)
    root_key = args.root_key
    overrides = args.override

    yaml_data = yaml.safe_load(yaml_path.read_text())
    config = yaml_data[root_key]

    if overrides:
        apply_overrides(overrides, config)

    ctx = ChemRegridContext.from_yaml(config)
