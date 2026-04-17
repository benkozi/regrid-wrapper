#!/usr/bin/env bash

set -eu

cd ..

pytest -v src/test
mpirun -n 8 pytest -v -m "mpi and not integration" src/test
