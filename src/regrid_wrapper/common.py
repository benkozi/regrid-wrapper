import subprocess
from pathlib import Path
from typing import Any


def ncdump(path: Path) -> Any:
    ret = subprocess.check_output(["ncdump", "-h", str(path)])
    print(ret.decode(), flush=True)
    return ret
