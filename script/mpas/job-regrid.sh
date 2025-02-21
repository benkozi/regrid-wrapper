#!/usr/bin/env bash
#
#SBATCH --job-name=mpas-regrid
#SBATCH --account=epic
#SBATCH --qos=batch
#SBATCH --partition=hera
#SBATCH -t 00:05:00
#SBATCH --output=/home/Benjamin.Koziol/htmp/%x.out
#_SBATCH --output=/home/Benjamin.Koziol/htmp/%x_%j.out
#SBATCH --error=/home/Benjamin.Koziol/htmp/%x.err
#_SBATCH --error=/home/Benjamin.Koziol/htmp/%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1  # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks=1  # Total tasks should be nodes * tasks-per-node

set -e

RUNDIR=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/script/mpas
PYTHONDIR=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/src
CONDAENV=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/miniconda3/envs/regrid-wrapper

export PATH=${CONDAENV}/bin:${PATH}
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk
export PYTHONPATH=${PYTHONDIR}:${PYTHONPATH}

cd ${RUNDIR}
python regrid.py
#mpirun -np 1 python
