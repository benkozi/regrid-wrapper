#!/bin/bash
#SBATCH --time=0:01:00
#SBATCH --qos=normal
#SBATCH --partition=batch
#SBATCH --ntasks=8
#SBATCH --account=epic
#SBATCH --job-name=test_mpirun
#SBATCH --output=test_mpirun.out

set -xue

CONDA_ENV=/glade/derecho/scratch/benkoz/sandbox/srw/ufs-srweather-app/conda/envs/srw_sd
PATH=${CONDA_ENV}/bin:${PATH}

export ESMFMKFILE=${CONDA_ENV}/lib/esmf.mk

which mpirun
which python

mpirun -n 8 python test_mpirun.py
