# Format and backend notes

## Tables

- CSV/TXT/TSV: pandas; delimiter inferred unless the extension is TSV.
- Excel: pandas with openpyxl for XLSX or xlrd for legacy XLS.
- Use `--size-variable` whenever more than one numeric non-coordinate column exists.

## NetCDF and Zarr

- Use xarray. NetCDF may require netCDF4, h5netcdf, or scipy. Zarr requires zarr.
- Coordinates may be 1-D rectilinear or matching 2-D curvilinear arrays.
- Supply `--select level=0` or similar before `--reduce` when a specific slice is scientifically intended.

## GRIB

- Use xarray with the cfgrib engine; cfgrib requires ecCodes.
- Heterogeneous GRIB messages may need filtering before this script. Convert to a coherent NetCDF when one file cannot open as one dataset.

## GeoTIFF

- Use rasterio. Pixel centers become bubble coordinates.
- Geographic rasters plot directly. Projected rasters require `--allow-reproject`; the script transforms pixel-center coordinates to EPSG:4326 rather than resampling values.
- Select a 1-based raster band with `--band`.

## HDF5 and HDF-EOS

- First try xarray for CF-compatible HDF5. Otherwise use h5py and search numeric datasets by leaf names.
- Override ambiguous full dataset paths with `--lat-name`, `--lon-name`, and `--size-variable`.
- HDF4 requires pyhdf or conversion to HDF5/NetCDF. HDF-EOS swath geolocation arrays must match the science-field shape.

## Common failures

- Missing optional backend: install the named package in the active environment; do not relabel or convert the file silently.
- Longitude in 0–360: accepted and normalized to −180–180 for plotting; recorded in stats.
- Projected x/y called lon/lat: verify units or CRS. Do not interpret meters as degrees.
- Natural Earth coastline data unavailable: `--coastlines auto` skips coastlines with a warning; `on` lets Cartopy fetch/cache them when network is permitted.
