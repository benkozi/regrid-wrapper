import argparse
from pathlib import Path

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
