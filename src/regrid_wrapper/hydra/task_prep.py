import hydra
from omegaconf import DictConfig

from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.model.config import SmokeDustRegridConfig, ComponentKey
import xarray as xr


MAIN_JOB_TEMPLATE = """#!/usr/bin/env bash
#
#SBATCH --job-name={job_name}
#SBATCH --account=epic
#SBATCH --qos=batch
#_SBATCH --partition=bigmem
#SBATCH --partition=hera
#SBATCH -t {wall_time}
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={tasks_per_node}  # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks={ntasks}  # Total tasks should be nodes * tasks-per-node

set -e

DIR=/scratch2/NAGAPE/epic/Ben.Koziol/sandbox/regrid-wrapper
CONDAENV=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/envs/regrid-wrapper

export PATH=${{CONDAENV}}/bin:${{PATH}}
export ESMFMKFILE=${{CONDAENV}}/lib/esmf.mk
export PYTHONPATH=${{DIR}}/src:${{PYTHONPATH}}
export REGRID_WRAPPER_LOG_DIR={log_directory}

cd ${{REGRID_WRAPPER_LOG_DIR}}
mpirun -np {ntasks} python ${{DIR}}/src/regrid_wrapper/hydra/run_operations.py
"""


def do_task_prep(cfg: SmokeDustRegridConfig) -> None:
    logger = LOGGER.getChild("do_task_prep")
    logger.info(cfg)
    logger.info("creating run directories")
    cfg.root_output_directory.mkdir(exist_ok=False, parents=True)
    cfg.log_directory.mkdir(exist_ok=False)
    rrfs_grid = None
    for grid_key in cfg.target_grids:
        cfg.output_directory(grid_key).mkdir(exist_ok=False, parents=True)
        logger.info("copying rrfs grid")
        rrfs_grid = cfg.source_definition.rrfs_grids[grid_key]
        with xr.open_dataset(rrfs_grid.grid) as src:
            src.to_netcdf(cfg.model_grid_path(grid_key))
        logger.info("copying rave grid")
        with xr.open_dataset(
            cfg.source_definition.components[ComponentKey.RAVE_GRID].grid
        ) as src:
            src.to_netcdf(cfg.rave_grid_path(grid_key))
    logger.info("creating main job script")
    assert rrfs_grid is not None
    with open(cfg.main_job_path, "w") as f:
        template = MAIN_JOB_TEMPLATE.format(
            job_name=cfg.root_output_directory.name,
            nodes=rrfs_grid.nodes,
            ntasks=rrfs_grid.nodes * rrfs_grid.tasks_per_node,
            log_directory=cfg.log_directory,
            wall_time=rrfs_grid.wall_time,
            tasks_per_node=rrfs_grid.tasks_per_node,
        )
        logger.info(template)
        f.write(template)


@hydra.main(version_base=None, config_path="conf", config_name="smoke-dust-config")
def do_task_prep_cli(cfg: DictConfig) -> None:
    logger = LOGGER.getChild("regrid_wrapper_app")
    logger.info("start")
    sd_cfg = SmokeDustRegridConfig.model_validate(cfg)
    do_task_prep(sd_cfg)
    logger.info("success")


if __name__ == "__main__":
    do_task_prep_cli()
