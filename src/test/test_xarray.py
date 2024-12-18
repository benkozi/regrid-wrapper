from pathlib import Path
import xarray as xr


def test_resizing(bin_dir: Path, tmp_path: Path) -> None:
    path = bin_dir / "RRFS_NA_3km/veg_map.nc"
    out_path = tmp_path / "out.nc"
    with xr.open_dataset(path) as ds:
        print(ds)
        ds["grid_lont"] = [1, 2, 3]
        arr = ds["geolat"]
        print(arr.attrs)
        print(ds)
