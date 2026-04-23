from functools import cached_property
from pathlib import Path

from pydantic import Field

from regrid_wrapper.app.chem_regrid.dataset.config.model import ChemRegridDataset
from regrid_wrapper.app.chem_regrid.dataset.context import DatasetName
from regrid_wrapper.common import RwBaseModel


class ChemRegridContext(RwBaseModel):
    """This is the API class for the regridding implementation. These fields may be customized by
    users."""

    dataset_name: DatasetName
    workdir: Path
    input_dir: Path
    output_dir: Path
    weight_dir: Path
    cycle: str = Field(pattern=r"^\d{10}$")  # Validates YYYYMMDDHH format
    mesh_name: str
    input_mesh_path: Path | None
    dst_path: Path | None
    ebb_dcycle: int
    fcst_length: int
    datasets_yml_path: Path = Path(__file__).parent / "dataset" / "config" / "datasets.yml"

    @cached_property
    def rw_input_mesh_path(self) -> Path:
        if self.input_mesh_path is None:
            return self.workdir / f"mpas_{self.dataset_name.value}-{self.mesh_name}_scrip.nc"
        return self.input_mesh_path

    @cached_property
    def rw_dst_path(self) -> Path:
        if self.dst_path is None:
            return self.workdir / "init.nc"
        return self.dst_path

    @cached_property
    def rw_desc_stats_out(self) -> Path:
        return self.workdir / f"desc_stats-{self.cycle}.csv"

    @cached_property
    def rw_dataset(self) -> ChemRegridDataset:
        return ChemRegridDataset.from_key(self.datasets_yml_path, self.dataset_name)

    @cached_property
    def rw_weight_path(self) -> Path:
        weight_path = self.weight_dir / (
            "weights_" + self.dataset_name.value + "-to-" + "mpas_" + self.mesh_name + "_" + self.rw_dataset.InterpMethod + ".nc"
        )
        return weight_path
