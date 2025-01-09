#!/usr/bin/env bash

RUNDIR=smoke-dust-fixed-files
CONDAENV=~/l/scratch/miniconda/envs/regrid-wrapper

cd ~/l/scratch/sandbox/regrid-wrapper || exit
git pull
rm -rf ${RUNDIR}

export PATH=${CONDAENV}/bin:${PATH}
export PYTHONPATH=$(pwd -LP)/src
export REGRID_WRAPPER_LOG_DIR=.
export ESMFMKFILE=${CONDAENV}/lib/esmf.mk

python ./src/test/test_read.py || exit

exit 0

python ./src/regrid_wrapper/hydra/task_prep.py || exit

cd ${RUNDIR}/logs || exit
sbatch ../main-job.sh || exit
squeue -u Benjamin.Koziol -i 5
