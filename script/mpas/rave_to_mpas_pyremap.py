"""
Using https://github.com/MPAS-Dev/pyremap
Based on this example: https://github.com/MPAS-Dev/pyremap/blob/main/examples/make_mpas_to_lat_lon_mapping.py

pyremap creates temporary SCRIP files for the src and dst
and then runs ESMF_RegridWeightGen with those
"""

from pathlib import Path

import numpy as np
import xarray as xr
import sys

# sys.path.append("/mnt/lfs5/BMC/rtwbl/Jordan/src/MPAS/input/scripts/pyremap")
from pyremap import (
    MpasCellMeshDescriptor,
    Remapper,
    LatLonGridDescriptor,
    LatLon2DGridDescriptor,
)

p_mpas_grid = Path(
    "/mnt/lfs5/BMC/gsd-fv3-dev/Haiqin.Li/MPAS-Smoke/na15km_2024072000/na15km.init.nc"
)
dst = MpasCellMeshDescriptor(p_mpas_grid, "na15km.init")


# static_file = sys.argv[
#     1
# ]  # "/lfs5/BMC/rtwbl/Jordan/src/MPAS/input/emissions/anthro/GRAPES/"+sector+"/202101/satdy/GRA2PESv1.0_"+sector+"_202101_satdy_00to11Z.nc"
static_file = " /mnt/lfs5/BMC/rtwbl/Jordan/src/MPAS/input/emissions/fire/RAVE-HrlyEmiss-3km_v1r3_blend_s202407240000000_e202407240059590_c202407240203140.nc"
static_fid = xr.open_dataset(static_file)
lat = static_fid["grid_latt"]  # .values.ravel()
lon = static_fid["grid_lont"]  # .values.ravel()


src = LatLon2DGridDescriptor.read(
    latVarName="grid_latt", lonVarName="grid_lont", fileName=static_file
)

# Global
dst.regional = True
src.regional = True

# method = "bilinear"
method = "conserve"
# method = "neareststod"
# p_weights = "/mnt/lfs5/BMC/rtwbl/Jordan/src/MPAS/input/scripts/weights_RAVE_to_mpas_na15km_conserve.nc"
p_weights = "/home/Benjamin.Koziol/htmp/weights_RAVE_to_mpas_na15km_conserve.nc"
remapper = Remapper(src, dst, p_weights)
# if not p_weights.is_file():
remapper.esmf_build_map(
    method=method,
    mpi_tasks=1,
    include_logs=True,
    tempdir="/home/Benjamin.Koziol/htmp",
)

# Do some remapping
ds_data = static_fid
ds_remapped = remapper.remap(ds_data[["FRE", "FRP_MEAN", "PM25", "NH3", "SO2"]])
ds_remapped.to_netcdf("RAVE_remapped.nc")
ds_data.close()
