import glob
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path
from typing import Iterator

import esmpy
import numpy as np

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.context.comm import COMM, reconcile_bounds
from regrid_wrapper.esmpy.field_wrapper import FieldWrapper, copy_nc_variable, open_nc, set_variable_data


def create_ngfs_sparse_mesh(lat_1d: np.ndarray, lon_1d: np.ndarray, resolution: float = 0.01) -> esmpy.Mesh:
    """
    Creates an esmpy.Mesh dynamically from 1-D point source data.
    Calculates the 4 corners of a square cell of size `resolution`
    around each center point in memory.
    This is the best approach since NGFS data are point-source (1-D),
    but we rarely have more than 1000 fires in the domain, so we
    can afford to keep this in memory instead of creating a file.
    """

    num_cells = len(lat_1d)
    if num_cells == 0:
        raise ValueError("must have at least one cell in the mesh")

    num_nodes = num_cells * 4
    d = resolution / 2.0

    node_lons = np.column_stack([lon_1d - d, lon_1d + d, lon_1d + d, lon_1d - d]).flatten()

    node_lats = np.column_stack([lat_1d - d, lat_1d - d, lat_1d + d, lat_1d + d]).flatten()

    node_coords = np.empty(num_nodes * 2, dtype=np.float64)
    node_coords[0::2] = node_lons
    node_coords[1::2] = node_lats

    node_ids = np.arange(1, num_nodes + 1, dtype=np.int32)
    node_owners = np.full(num_nodes, COMM.rank, dtype=np.int32)

    element_ids = np.arange(1, num_cells + 1, dtype=np.int32)
    element_types = np.full(num_cells, esmpy.MeshElemType.QUAD, dtype=np.int32)

    # CRITICAL FIX: esmpy expects 0-based indexing for connectivity!
    element_conn = np.arange(0, num_nodes, dtype=np.int32)

    # Explicitly set spherical coordinates
    mesh = esmpy.Mesh(parametric_dim=2, spatial_dim=2, coord_sys=esmpy.CoordSys.SPH_DEG)

    mesh.add_nodes(node_count=num_nodes, node_ids=node_ids, node_coords=node_coords, node_owners=node_owners)

    mesh.add_elements(element_count=num_cells, element_ids=element_ids, element_types=element_types, element_conn=element_conn)

    return mesh


def process_ngfs_file(
    ctx: AbstractDatasetRegridContext, file_path: Path, dst_fwrap: FieldWrapper, resolution: float = 0.01
) -> None:
    """Dynamically builds a mesh for NGFS points, regrids, and writes the output."""
    CR_LOGGER.info(f"Processing NGFS file: {file_path}")

    # 1. Read NGFS Coordinates AND Area
    with open_nc(file_path, mode="r") as ds:
        lats = ds.variables["lat"][:].filled(np.nan)
        lons = ds.variables["lon"][:].filled(np.nan)

        # Read the NGFS area (in km2)
        if "GRID_AREA" in ds.variables:
            grid_area = ds.variables["GRID_AREA"][:].filled(np.nan)
        else:
            CR_LOGGER.warning("GRID_AREA not found! Defaulting to 1.0 km2.")
            grid_area = np.ones_like(lats)

    # Filter out NaNs
    valid = ~np.isnan(lats) & ~np.isnan(lons) & ~np.isnan(grid_area)
    lats = lats[valid]
    lons = lons[valid]
    grid_area = grid_area[valid]

    # CRITICAL FIX: Convert -180/180 to 0/360 to match MPAS grid
    lons = lons % 360.0

    if len(lats) == 0:
        CR_LOGGER.warning("No valid fires in file.")
        return

    # 2. Build Sparse Source Mesh
    src_mesh = create_ngfs_sparse_mesh(lats, lons, resolution)

    # 3. Create Output NetCDF File (Header Info)
    if ctx.rank == 0:
        with open_nc(ctx.new_dst_path, mode="w", clobber=True, parallel=False) as dst_nc:
            dst_nc.createDimension("nCells", ctx.num_cells)
            if ctx.level_out_name is None:
                raise ValueError("level_out_name must be set for NGFS regridding")
            dst_nc.createDimension(ctx.level_out_name, ctx.level_out_size)
            dst_nc.createDimension("StrLen", 64)
            if ctx.time_size is not None and ctx.time_size > 1:
                dst_nc.createDimension("Time", ctx.time_size)
            elif ctx.time_size == 1:
                dst_nc.createDimension("Time")
            dst_nc.setncattr("created_at", str(datetime.now(timezone.utc)))
            dst_nc.setncattr("src_path", str(ctx.src_path))
            dst_nc.setncattr("dst_path", str(ctx.dst_path))

            # Copy base MPAS variables
            with open_nc(ctx.dst_path, mode="r", parallel=False) as src_nc:
                for varname in ("latCell", "lonCell", "areaCell", "xland", "xtime"):
                    copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)

    # 4. Process Each Variable
    for src_field in ctx.src_fields:
        CR_LOGGER.info(f"regridding NGFS {src_field.name=}")

        # Create Source Field dynamically
        src_field = esmpy.Field(src_mesh, name=src_field.name, meshloc=esmpy.MeshLoc.ELEMENT)

        # Map MPAS expected name to NGFS actual name
        if src_field.name == "PM25":
            ngfs_var_name = "EMIS_PM25"
        else:
            ngfs_var_name = src_field.name

        # Load the raw data
        with open_nc(file_path, mode="r") as ds:
            if ngfs_var_name in ds.variables:
                raw_data = ds.variables[ngfs_var_name][:].filled(0.0)[valid]
            else:
                CR_LOGGER.warning(f"Variable {ngfs_var_name} not found! Skipping.")
                continue

        # ---------------------------------------------------------
        # UNIT CONVERSIONS (Identical to RAVE logic)
        # ---------------------------------------------------------
        if src_field.name in ("PM25", "TPM"):
            # Convert from kg/hr to ug/m2/s (1e3 handles the km2 to m2 and kg to ug ratio)
            src_data = np.where(raw_data < 0.0, 0.0, raw_data * 1.0e3 / grid_area / 3600.0)
        elif src_field.name in ("FRE", "FRP_MEAN"):
            # For FRE, FRP: MW to W (1e6) cancels out with km2 to m2 (1e6)
            src_data = np.where(raw_data < 0.0, 0.0, raw_data / grid_area)
        else:
            src_data = np.where(raw_data < 0.0, 0.0, raw_data)

        src_field.data[:] = src_data

        # Create Dynamic Regridder
        regridder = esmpy.Regrid(
            srcfield=src_field,
            dstfield=dst_fwrap.value,
            regrid_method=esmpy.RegridMethod.CONSERVE,
            unmapped_action=esmpy.UnmappedAction.IGNORE,
        )

        # Apply Regridding
        dst_fwrap.data.fill(0.0)
        regridder(src_field, dst_fwrap)

        # Write to Output NetCDF
        local_bounds = (dst_fwrap.value.lower_bounds[0], dst_fwrap.value.upper_bounds[0])
        reconciled_bounds = reconcile_bounds(local_bounds)
        dims = src_field.create_dimension_collection(reconciled_bounds)

        with open_nc(ctx.new_dst_path, mode="a") as ds:
            var = ds.createVariable(
                src_field.name,  # Keep it as standard name in output!
                src_field.dtype,
                [dim.name[0] for dim in dims.value],
                fill_value=src_field.fill_value,
            )
            for k, v in src_field.attrs.items():
                setattr(var, k, v)

            # Multiply by areaCell for Power/Energy variables (back to total W in cell)
            if src_field.name in ("FRP_MEAN", "FRE"):
                area = np.asarray(ds.variables["areaCell"])
                area_subset = area[reconciled_bounds[0] : reconciled_bounds[1]]
                set_variable_data(var, dims, src_field.reshape_field_data(dst_fwrap.data * area_subset), collective=True)
            else:
                set_variable_data(var, dims, src_field.reshape_field_data(dst_fwrap.data), collective=True)

        # Clean up memory
        regridder.destroy()
        src_field.destroy()

    # Clean up mesh
    src_mesh.destroy()


def run_ngfs_regridding(regrid_context: AbstractDatasetRegridContext) -> None:
    from regrid_wrapper.app.chem_regrid.chem_regrid_impl import ChemRegridProcessor

    processor = ChemRegridProcessor(context=regrid_context)

    for date_to_process in regrid_context.dates_needed:
        # Construct the filename (Adjust the prefix 'ngfs_' if your files are named differently)
        # print("GAF debug: attempting to read: " + input_dir + "/NGFS_v0.31_" + date_to_process + "_0p01.nc")
        ngfs_paths = glob.glob(str(regrid_context.input_dir) + "/NGFS_v0.31_0p01_" + date_to_process + "0000.nc")

        if not ngfs_paths:
            print(f"ERROR: Missing NGFS file for {date_to_process}. Skipping.")
            exit(1)
            # TODO: perhaps add a helper similarly as I added for RAVE to search for the latest
            # available file in case that the current datetime does not exist
            continue

        ngfs_path = Path(ngfs_paths[0])
        new_dst_path = Path(str(regrid_context.output_dir) + "/" + regrid_context.mesh_name + "-NGFS-" + date_to_process + ".nc")
        print(f"GAF reading NGFS file: {ngfs_path}")

        # Update context paths for the current hour
        processor.context.src_path = ngfs_path
        processor.context.new_dst_path = new_dst_path

        # Execute the dynamic regridding for this specific hour's fires
        # Note that resolution is hard coded...
        process_ngfs_file(regrid_context, ngfs_path, processor.get_dst_fwrap(), resolution=0.01)

    CR_LOGGER.info("NGFS success")


class NGFS_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for NGFS (Next Generation Fire System) data."""

    def get_read_name(self, field_name: str) -> str:
        if field_name == "PM25":
            return "EMIS_PM25"
        return super().get_read_name(field_name)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        raise NotImplementedError("NGFS not yet supported")

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        # Determine the cycle dates to process +%Y%m%d%H
        # This is for RETROS (using current datetime, not day before)
        for i in range(25):  # GAF retro current day emissions
            if self.ebb_dcycle == 1:  # Same-day emissions
                x = self.dt_spec.datetime + timedelta(hours=i)
            elif self.ebb_dcycle == -1 or self.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = self.dt_spec.datetime - timedelta(hours=i)
            else:
                CR_LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = self.dt_spec.datetime + timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed
