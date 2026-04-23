from pathlib import Path

from regrid_wrapper.app.chem_regrid.dataset.context import DatasetName
from regrid_wrapper.app.chem_regrid.dataset.context.base import InterpMethod
from regrid_wrapper.common import RwBaseModel


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
    InterpMethod: InterpMethod

    @classmethod
    def from_key(cls, yaml_path: Path, key: DatasetName) -> "ChemRegridDataset":

        def retriever(data: dict) -> dict:
            ret = data[key.value]
            ret["key"] = key
            return ret

        return cls.from_yaml_file(yaml_path, retriever=retriever)
