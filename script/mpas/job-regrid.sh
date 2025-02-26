#!/usr/bin/env bash
#
#SBATCH --job-name=mpas-regrid
#SBATCH --account=epic
#SBATCH --qos=batch
#SBATCH --partition=hera
#SBATCH -t 00:30:00
#SBATCH --output=/home/Benjamin.Koziol/htmp/out/%x.out
#_SBATCH --output=/home/Benjamin.Koziol/htmp/out/%x_%j.out
#SBATCH --error=/home/Benjamin.Koziol/htmp/out/%x.err
#_SBATCH --error=/home/Benjamin.Koziol/htmp/out/%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=24 # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks=24  # Total tasks should be nodes * tasks-per-node

set -xe

export REGRID_WRAPPER_LOG_DIR=/home/Benjamin.Koziol/htmp/out
SCRIPT=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/script/mpas/regrid.py
PYTHONDIR=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/src
CONDAENV=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/miniconda3/envs/regrid-wrapper

export PATH=${CONDAENV}/bin:${PATH}
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk
export PYTHONPATH=${PYTHONDIR}:${PYTHONPATH}

cd ${REGRID_WRAPPER_LOG_DIR}
mkdir ${REGRID_WRAPPER_LOG_DIR}/logs
mpirun -n 24 python ${SCRIPT} || mv *.log *.ESMF_LogFile logs || echo "could not move logs"
