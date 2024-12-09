#!/usr/bin/env bash

set -e

# conda activate declarative-regridding

cd /opt/project
rm ./*.ESMF_LogFile || echo "no ESMF log files"
mpirun -n 8 pytest -sv src/test/test_esmpy.py::test_regridding_weights
