import argparse
from pathlib import Path
from typing import Any

from regrid_wrapper.context.logging import LOGGER


def mpas_to_ugrid_cli(args: argparse.Namespace) -> None:
    from regrid_wrapper.mpas.mpas_to_ugrid import run_conversion

    input_path = Path(args.input)
    output_path = Path(args.output)

    if output_path.exists():
        if args.clobber:
            LOGGER.info(f"Output file {output_path} exists, clobbering.")
            output_path.unlink()
        else:
            msg = f"Output file {output_path} exists and --clobber is not set. Exiting."
            LOGGER.error(msg)
            raise IOError(msg)

    run_conversion(input_path, output_path)


def add_mpas_to_ugrid_parser(subparsers: Any) -> None:
    # mpas-to-ugrid sub-command
    parser_m2u = subparsers.add_parser("mpas-to-ugrid", help="Convert MPAS grid to UGRID format")
    parser_m2u.add_argument("-i", "--input", required=True, help="Input MPAS grid path")
    parser_m2u.add_argument("-o", "--output", required=True, help="Output UGRID path")

    clobber_group = parser_m2u.add_mutually_exclusive_group()
    clobber_group.add_argument(
        "--clobber",
        action="store_true",
        required=False,
        default=False,
        help="Overwrite output file if it exists (default to False)",
    )
