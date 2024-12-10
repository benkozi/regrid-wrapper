#!/usr/bin/env bash
#
#SBATCH --job-name=RAVE.to.RRFS_3km
#SBATCH --account=epic
#SBATCH --qos=batch
#_SBATCH --partition=bigmem
#SBATCH --partition=hera
#SBATCH -t 00:05:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=24  # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks=24  # Total tasks should be nodes * tasks-per-node

set -e

DIR=/scratch2/NAGAPE/epic/Ben.Koziol/sandbox/regrid-wrapper
CONDAENV=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/envs/regrid-wrapper

export PATH=${CONDAENV}/bin:${PATH}
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk
export PYTHONPATH=${DIR}/src:${PYTHONPATH}

cd ${DIR}/logs
mpirun -np 24 python ../operations/RAVE.to.RRFS_3km/main.py
