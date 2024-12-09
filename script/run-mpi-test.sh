#!/usr/bin/env bash

set -e

cd /opt/project
mpirun -n 2 pytest -m "mpi" src/test
