#!/bin/bash
#PBS -A NRAL0032
#PBS -N test_mpirun
#PBS -q main
#PBS -l walltime=00:01:00
#PBS -l select=1:mpiprocs=8

set -xue

CONDA_ENV=/glade/derecho/scratch/benkoz/sandbox/srw/ufs-srweather-app/conda/envs/srw_sd
PATH=${CONDA_ENV}/bin:${PATH}

export ESMFMKFILE=${CONDA_ENV}/lib/esmf.mk

which mpirun
which python

mpirun -n 8 python test_mpirun.py
