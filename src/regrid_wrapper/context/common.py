from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator


def _validate_path_(value: str | Path) -> Path:
    value = Path(value)
    return value.expanduser().resolve()


PathType = Annotated[Path, BeforeValidator(_validate_path_)]
