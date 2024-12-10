#!/usr/bin/env bash

set -e

export PATH=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/envs/regrid-wrapper/bin:${PATH}
export ESMFMKFILE=/scratch2/NAGAPE/epic/Ben.Koziol/miniconda/envs/regrid-wrapper/lib/esmf.mk

cd /scratch2/NAGAPE/epic/Ben.Koziol/sandbox/regrid-wrapper
pytest src/test
