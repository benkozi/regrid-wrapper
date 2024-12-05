from typing import List

from pydantic import BaseModel


class RegridOperation(BaseModel):
    src: str
    dst: str
    fields: List[str]
