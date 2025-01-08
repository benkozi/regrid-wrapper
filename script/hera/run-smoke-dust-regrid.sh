#!/usr/bin/env bash

RUNDIR=smoke-dust-fixed-files

cd ~/l/scratch/sandbox/regrid-wrapper || exit
git pull
rm -rf ${RUNDIR}

export PYTHONPATH=$(pwd -LP)/src
export REGRID_WRAPPER_LOG_DIR=.

~/l/scratch/miniconda/envs/regrid-wrapper/bin/python ./src/regrid_wrapper/hydra/task_prep.py

cd ${RUNDIR}/logs || exit
sbatch ../main-job.sh
squeue -u Benjamin.Koziol -i 5
