#!/bin/bash
#SBATCH --account=ap-fc
#SBATCH --qos=batch
#SBATCH --partition=bigmem
#SBATCH -t 08:00:00
#SBATCH --nodes=15
#SBATCH --ntasks-per-node=24  # Assuming 24 cores per node, utilize them fully
#SBATCH --ntasks=360  # Total tasks should be nodes * tasks-per-node


module load intel impi
cd /scratch1/BMC/acomp/Johana/HWP_tools/rave_interp_RRFS
#source /scratch1/BMC/acomp/Johana/miniconda/bin/activate xesmf_env
#python xempy_nearest.dtos_model_out.py

source /scratch1/BMC/acomp/Johana/miniconda/bin/activate interpol_esmpy
mpirun -np 360 python prod_weigh_grib2.py
