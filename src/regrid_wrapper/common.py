import subprocess
from pathlib import Path
from typing import Any


def ncdump(path: Path, header_only: bool = True) -> Any:
    args = ["ncdump"]
    if header_only:
        args.append("-h")
    args.append(str(path))
    ret = subprocess.check_output(args)
    print(ret.decode(), flush=True)
    return ret
