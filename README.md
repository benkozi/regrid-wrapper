# Environment Setup

> conda env create -f environment.yaml
> 
* Add `REGRID_WRAPPER_LOG_DIR` location to environment or `.env`.

# Testing

> pytest src/test

For parallel:

> mpirun -n 8 pytest -m mpi src/test
