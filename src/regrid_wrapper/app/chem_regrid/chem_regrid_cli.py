import argparse
from pathlib import Path

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
