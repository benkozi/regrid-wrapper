from typing import Iterator

from regrid_wrapper.concrete.emi_data import EMI_DATA_ENV, EmiData
from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.concrete.rrfs_dust_data import RRFS_DUST_DATA_ENV, RrfsDustData
from regrid_wrapper.concrete.rrfs_smoke_dust_veg_map import RrfsSmokeDustVegetationMap
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.model.config import SmokeDustRegridConfig, ComponentKey
from regrid_wrapper.model.spec import (
    GenerateWeightFileAndRegridFields,
    GenerateWeightFileSpec,
)
from regrid_wrapper.strategy.operation import AbstractRegridOperation


def iter_operations(cfg: SmokeDustRegridConfig) -> Iterator[AbstractRegridOperation]:
    logger = LOGGER.getChild("iter_operations")
    for target_grid in cfg.target_grids:
        for target_component in cfg.target_components:
            name = f"{target_grid}-{target_component}"
            logger.debug(f"creating operation: {name}")
            output_directory = cfg.output_directory(target_grid)
            model_grid_path = cfg.model_grid_path(target_grid)
            match target_component:
                case ComponentKey.VEG_MAP:
                    spec = GenerateWeightFileAndRegridFields(
                        src_path=cfg.source_definition.components[
                            target_component
                        ].grid,
                        dst_path=model_grid_path,
                        output_weight_filename=output_directory
                        / f"weights-veg_map-NA_3km-to-{target_grid}.nc",
                        output_filename=output_directory / "veg_map.nc",
                        fields=["emiss_factor"],
                        name=name,
                    )
                    yield RrfsSmokeDustVegetationMap(spec=spec)
                case ComponentKey.RAVE_GRID:
                    spec = GenerateWeightFileSpec(
                        src_path=cfg.source_definition.components[
                            target_component
                        ].grid,
                        dst_path=model_grid_path,
                        output_weight_filename=output_directory / "weight_file.nc",
                        name=name,
                    )
                    yield RaveToRrfs(spec=spec)
                case ComponentKey.DUST:
                    spec = GenerateWeightFileAndRegridFields(
                        src_path=cfg.source_definition.components[
                            target_component
                        ].grid,
                        dst_path=model_grid_path,
                        output_weight_filename=output_directory
                        / f"weights-dust_data-to-{target_grid}.nc",
                        output_filename=output_directory / "dust12m_data.nc",
                        fields=RRFS_DUST_DATA_ENV.fields,
                        name=name,
                    )
                    yield RrfsDustData(spec=spec)
                case ComponentKey.EMI:
                    spec = GenerateWeightFileAndRegridFields(
                        src_path=cfg.source_definition.components[
                            target_component
                        ].grid,
                        dst_path=model_grid_path,
                        output_weight_filename=output_directory
                        / f"weights-dust_data-to-{target_grid}.nc",
                        output_filename=output_directory / "emi_data.nc",
                        esmpy_debug=False,
                        name="emi-data",
                        fields=EMI_DATA_ENV.fields,
                    )
                    yield EmiData(spec=spec)
                case _:
                    raise NotImplementedError(
                        f"Unsupported target component {target_component}"
                    )
