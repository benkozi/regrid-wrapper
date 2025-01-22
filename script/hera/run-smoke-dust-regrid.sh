#!/usr/bin/env bash

set -e

RUNDIR=smoke-dust-fixed-files
CONDAENV=~/l/scratch/miniconda/envs/regrid-wrapper
#CONDAENV=~/miniconda3/envs/tmp-uni

cd ~/l/scratch/sandbox/regrid-wrapper || exit
git pull
rm -rf ${RUNDIR} || echo "run directory does not exist"

export PATH=${CONDAENV}/bin:${PATH}
export PYTHONPATH=$(pwd -LP)/src
export REGRID_WRAPPER_LOG_DIR=.
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk

python ./src/regrid_wrapper/hydra/task_prep.py || exit

cd ${RUNDIR}/logs || exit
sbatch ../main-job.sh || exit
squeue -u Benjamin.Koziol -i 30
