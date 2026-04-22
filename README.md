# CLI Usage

The `rw` command provides a set of command-line tools for regridding.

## MPAS to UGRID Conversion

1. `conda env create -f environment-uxarray.yaml`
2. `cd <regrid-wrapper src>`
3. `conda run -n regrid-wrapper-uxarray pip install -e .`
4. `export REGRID_WRAPPER_LOG_DIR=<path to log dir>`
4. `conda run -n regrid-wrapper-uxarray rw mpas-to-ugrid <flags>`

Convert an MPAS grid file to UGRID format:

```bash
usage: rw mpas-to-ugrid [-h] -i INPUT -o OUTPUT [--clobber]

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input MPAS grid path
  -o OUTPUT, --output OUTPUT
                        Output UGRID path
  --clobber             Overwrite output file if it exists (default is False)
```

# Docker Testing Instructions

Install Docker desktop: https://docs.docker.com/get-started/get-docker/

Start the container environment:

```
rw_root=<path to regrid-wrapper root> && \
  docker run --rm -it -v ${rw_root}:/opt/project deckyfre/regrid-wrapper-ci bash
```

Now inside the container:

```
cd /opt/project && \
  pytest src/test
```

... or mpi tests:

```bash
mpirun -n 8 pytest -m mpi src/test
```

# Adding a New Dataset

To add a new dataset to the regridding pipeline, follow these steps:

1.  **Update `DatasetName` Enum**: Add the new dataset key to the `DatasetName` enum in `src/regrid_wrapper/app/chem_regrid/dataset/model.py`.
2.  **Add Configuration**: Add a new entry to `src/regrid_wrapper/app/chem_regrid/dataset/config/datasets.yml` following the schema described above.
3.  **Create Regrid Context Subclass**: In `src/regrid_wrapper/app/chem_regrid/dataset/dataset_regrid_context.py`, create a new subclass of `AbstractDatasetRegridContext` (e.g., `MY_DATASET_DatasetRegridContext`).
    *   Implement `iter_file_pairs` to define how source and destination files are paired.
    *   Override `update_src_field_wrapper`, `transform_regridded_data`, or `post_regrid_processing` if dataset-specific logic is needed.
4.  **Register the Subclass**: Add the new context class to the `klasses` dictionary in the `get_regrid_context_class` factory function within `src/regrid_wrapper/app/chem_regrid/dataset/regrid_context.py`.

## Dataset Configuration

Datasets are configured in `src/regrid_wrapper/app/chem_regrid/dataset/config/datasets.yml`. Each entry defines how a specific dataset should be read and regridded.

### Dataset Schema

| Field | Description |
|---|---|
| `field_names` | List of variable names to be regridded from the source file. |
| `x_center` | Variable name for longitude centers. |
| `y_center` | Variable name for latitude centers. |
| `x_dim` | Dimension name for the X (longitude) axis. |
| `y_dim` | Dimension name for the Y (latitude) axis. |
| `x_corner` | (Optional) Variable name for longitude corners. Set to `null` if not available. |
| `y_corner` | (Optional) Variable name for latitude corners. Set to `null` if not available. |
| `x_corner_dim` | (Optional) Dimension name for longitude corners. |
| `y_corner_dim` | (Optional) Dimension name for latitude corners. |
| `level_in_name` | (Optional) Name of the vertical level dimension in the source file. |
| `level_out_name` | Name of the vertical level dimension in the output file. |
| `level_out_size` | Number of vertical levels in the output. Set to `0` for 2D data. |
| `time_name` | (Optional) Name of the time dimension in the source file. |
| `time_size` | Number of time steps. Set to `0` if time dimension is not used. |
| `InterpMethod` | ESMF interpolation method (e.g., `CONSERVE`, `BILINEAR`, `NEAREST_STOD`). |

### Example Entry

```yaml
MY_DATASET:
  field_names:
    - PM25
    - SO2
  x_center: lon
  y_center: lat
  x_dim: x
  y_dim: y
  x_corner: null
  y_corner: null
  x_corner_dim: null
  y_corner_dim: null
  level_in_name: null
  level_out_name: nkanthro
  level_out_size: 1
  time_name: time
  time_size: 1
  InterpMethod: CONSERVE
```
