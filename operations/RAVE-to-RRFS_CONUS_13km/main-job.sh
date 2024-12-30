#!/usr/bin/env bash
#
#SBATCH --job-name=RAVE-to-RRFS_CONUS_13km
#SBATCH --account=epic
#SBATCH --qos=batch
#_SBATCH --partition=bigmem
#SBATCH --partition=hera
#SBATCH -t 04:00:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=24  # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks=48  # Total tasks should be nodes * tasks-per-node

set -e

DIR=/scratch2/NAGAPE/epic/Ben.Koziol/sandbox/regrid-wrapper
CONDAENV=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/envs/regrid-wrapper
LOGDIR=${DIR}/logs/RAVE-to-RRFS_CONUS_13km

export PATH=${CONDAENV}/bin:${PATH}
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk
export PYTHONPATH=${DIR}/src:${PYTHONPATH}
export REGRID_WRAPPER_LOG_DIR=${LOGDIR}

mkdir -p ${LOGDIR}
cd ${LOGDIR}
mpirun -np 48 python ${DIR}/operations/RAVE-to-RRFS_CONUS_13km/main.py
