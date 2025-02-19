#!/usr/bin/env bash

set -e

RUNDIR=smoke-dust-fixed-files
CONDAENV=~/l/stmp2/miniconda3/envs/regrid-wrapper

cd ~/l/stmp2/sandbox/regrid-wrapper || exit
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
