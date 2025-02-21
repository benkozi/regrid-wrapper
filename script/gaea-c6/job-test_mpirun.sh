#!/bin/bash
#SBATCH --clusters=c6
#SBATCH --time=0:01:00
#SBATCH --qos=normal
#SBATCH --partition=batch
#SBATCH --ntasks=8
#SBATCH --account=bil-fire8
#SBATCH --job-name=test_mpirun
#SBATCH --output=/autofs/ncrc-svm1_home2/Benjamin.Koziol/htmp/test_mpirun.out

set -xue

CONDA_ENV=/gpfs/f6/bil-fire8/scratch/Benjamin.Koziol/sandbox/srw/ufs-srweather-app/conda/envs/srw_sd
PATH=${CONDA_ENV}/bin:${PATH}

export ESMFMKFILE=${CONDA_ENV}/lib/esmf.mk

which mpirun
which python

mpirun -n 8 python test_mpirun.py
