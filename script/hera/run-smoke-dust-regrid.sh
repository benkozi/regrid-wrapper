#!/usr/bin/env bash

cd ~/l/scratch/sandbox/regrid-wrapper || exit
git pull
rm -rf foo-test

export PYTHONPATH=$(pwd -LP)/src
export REGRID_WRAPPER_LOG_DIR=.

~/l/scratch/miniconda/envs/regrid-wrapper/bin/python ./src/regrid_wrapper/hydra/task_prep.py

cd foo-test/logs || exit
sbatch ../main-job.sh
squeue -u Benjamin.Koziol -i 5
