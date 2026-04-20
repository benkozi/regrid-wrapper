import argparse
from typing import Any


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


def add_verify_parser(subparsers: Any) -> None:
    # verify sub-command
    parser_verify = subparsers.add_parser("verify", help="Verify data files using nccmp.")
    parser_verify.add_argument(
        "--yaml-path", type=str, required=True, help="Path to YAML file containing the configuration's root key"
    )
    parser_verify.add_argument(
        "--root-key", type=str, default="rw-verify", help="If provided, use this key when extracting the root configuration"
    )


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="rw", description="regrid-wrapper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_mpas_to_ugrid_parser(subparsers)
    add_verify_parser(subparsers)
    add_chem_regrid_parser(subparsers)

    args = parser.parse_args()

    if args.command == "mpas-to-ugrid":
        from regrid_wrapper.app.mpas_to_ugrid_cli import mpas_to_ugrid_cli

        mpas_to_ugrid_cli(args)
    elif args.command == "verify":
        from regrid_wrapper.app.verify.verify_cli import verify_cli

        verify_cli(args)
    elif args.command == "chem-regrid":
        from regrid_wrapper.app.chem_regrid.chem_regrid_cli import chem_regrid_cli

        chem_regrid_cli(args)


if __name__ == "__main__":
    main()
