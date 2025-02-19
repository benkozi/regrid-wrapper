import xarray as xr


PATH = "/mnt/lfs5/BMC/rtwbl/Jordan/src/MPAS/input/emissions/fire/RAVE-HrlyEmiss-3km_v1r3_blend_s202407240000000_e202407240059590_c202407240203140.nc"

with xr.open_dataset(PATH) as ds:
    da = ds["FRE"]
    print(da.max())
