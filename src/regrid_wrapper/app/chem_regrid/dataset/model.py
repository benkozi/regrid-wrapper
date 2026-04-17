from enum import StrEnum, unique
from pathlib import Path

from regrid_wrapper.common import RwBaseModel


@unique
class DatasetName(StrEnum):
    RAVE = "RAVE"
    GRA2PES = "GRA2PES"
    NEMO_RWC = "NEMO_RWC"
    NEMO_ANTHRO = "NEMO_ANTHRO"
    FMC = "FMC"
    PECM = "PECM"
    NARR = "NARR"
    ECOREGION = "ECOREGION"
    FENGSHA_2D = "FENGSHA_2D"
    FENGSHA_2D_Time = "FENGSHA_2D_Time"
    NGFS = "NGFS"
    GOES = "GOES"


class ChemRegridDataset(RwBaseModel):
    key: DatasetName
    field_names: tuple[str, ...]
    x_center: str
    y_center: str
    x_dim: str
    y_dim: str
    x_corner: str | None
    y_corner: str | None
    x_corner_dim: str | None
    y_corner_dim: str | None
    level_in_name: str | None
    level_out_name: str | None
    level_out_size: int | None
    time_name: str | None
    time_size: int | None
    InterpMethod: str

    @classmethod
    def from_key(cls, yaml_path: Path, key: DatasetName) -> "ChemRegridDataset":

        def retriever(data: dict) -> dict:
            ret = data[key.value]
            ret["key"] = key
            return ret

        return cls.from_yaml_file(yaml_path, retriever=retriever)
