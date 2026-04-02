import argparse

from regrid_wrapper.app.chem_regrid.chem_regrid_cli import add_chem_regrid_parser, chem_regrid_cli
from regrid_wrapper.app.mpas_to_ugrid_cli import add_mpas_to_ugrid_parser, mpas_to_ugrid_cli
from regrid_wrapper.app.verify.verify_cli import add_verify_parser, verify_cli


def main() -> None:
    parser = argparse.ArgumentParser(prog="rw", description="regrid-wrapper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_mpas_to_ugrid_parser(subparsers)
    add_verify_parser(subparsers)
    add_chem_regrid_parser(subparsers)

    args = parser.parse_args()

    if args.command == "mpas-to-ugrid":
        mpas_to_ugrid_cli(args)
    elif args.command == "verify":
        verify_cli(args)
    elif args.command == "chem-regrid":
        chem_regrid_cli(args)


if __name__ == "__main__":
    main()
