#!/usr/bin/env bash

set -e

cd /opt/project
mpirun -n 8 pytest -m "mpi" src/test
