---
name: plot-geospatial-bubble-map
description: Create publication-ready proportional-symbol (bubble) maps from geolocated point or gridded geoscience data. Use when circle area should encode data magnitude and optional color should encode a second variable or classes; for global, regional, or longitude/latitude maps from NetCDF, NC4, CSV, TSV, TXT, Excel, GeoTIFF/TIFF, HDF5/HDF-EOS, GRIB/GRB, or Zarr inputs; and for requests mentioning bubble maps, graduated circles, proportional symbols, geospatial scatter plots, station maps, event frequency, or value-sized circles.
---

# Plot Geospatial Bubble Map

Create a global or regional proportional-symbol map with `scripts/plot_bubble_map.py`. Treat marker **area**, not radius, as proportional to magnitude by default.

## Workflow

1. Inspect the file and identify longitude, latitude, size variable, and optional color variable. Ask only when several choices remain scientifically plausible.
2. Decide whether non-spatial dimensions need `first`, `mean`, `sum`, `max`, or a named index. Never collapse them silently.
3. Plot with an appropriate projection and extent. Use Plate Carrée for ordinary regional maps and Equal Earth or Robinson for global maps.
4. Inspect the rendered figure and sibling `*.stats.json`. Check symbol overlap, legend truthfulness, clipping, and coordinate order.
5. Return both files and report variables, reduction, point thinning, marker-size transform, projection, and DPI.

## Quick start

```bash
python scripts/plot_bubble_map.py stations.csv \
  --size-variable elevation --color-variable frequency \
  --title "Annual event frequency" --size-unit m --color-unit events/a \
  --projection platecarree --extent -130 -65 24 52 \
  --output bubble_map.png
```

For a gridded file:

```bash
python scripts/plot_bubble_map.py data.nc \
  --size-variable magnitude --color-variable frequency \
  --reduce mean --projection equalearth --global \
  --output global_bubbles.png
```

## Data behavior

- Auto-detect table columns named like `lon|longitude|x` and `lat|latitude|y`; override with `--lon-name` and `--lat-name`.
- Read NetCDF and Zarr with xarray; GRIB with cfgrib; GeoTIFF with rasterio; generic HDF5 with h5py; CSV/TSV/TXT and Excel with pandas.
- For tables, require one row per observation. Preserve duplicate coordinates because multiple events at one station can be meaningful; use `--aggregate mean|sum|max` only when requested.
- For gridded data, accept 1-D or 2-D longitude/latitude coordinates. Reduce extra dimensions only with `--reduce`; default to rejecting ambiguous extra dimensions.
- For GeoTIFF, require a geographic CRS unless `--allow-reproject` is used; reproject to EPSG:4326 through rasterio.
- Limit dense grids using deterministic spatial stride via `--max-points`; record the retained count. Do not call thinning an aggregation.
- Omit non-finite coordinates and values. By default omit zero markers and reject negative size values; use `--absolute-size` only when magnitude is intended.

## Visual encoding

- Use `--size-transform linear` by default. Matplotlib marker `s` is area, so circle area is proportional to data above the minimum visible-area clip. Use `sqrt` or `log1p` only to reveal highly skewed data and disclose the transform.
- Set displayed marker-area bounds with `--min-area` and `--max-area` in points squared.
- Use `--size-breaks` for exact legend values or robust representative values otherwise.
- Use `--size-bins` with increasing edges and optional `--size-labels` when the user requests graduated size classes. Assign one fixed marker area per interval and use the same intervals in the legend.
- Use a continuous colorbar by default. Use `--color-bins` with monotonically increasing edges and optional `--color-labels` to reproduce categorical legends such as `<1, 1–1.5, 1.5–2, 2+`.
- Keep a vertical colorbar aligned to the full height of the map axes unless the user requests a compact inset.
- Use a sequential colormap for magnitude, diverging for signed anomalies, and qualitative colors only for categories.
- Keep marker edges thin and neutral; use alpha cautiously because overlap alters perceived color.

## Key controls

- `--projection platecarree|robinson|equalearth|mollweide|mercator`
- `--global` or `--extent WEST EAST SOUTH NORTH`; otherwise infer a padded regional extent.
- `--reduce first|mean|sum|max|min` and `--select dim=index` for non-spatial dimensions.
- `--band` for 1-based GeoTIFF band selection; for a GeoTIFF color variable, pass its band number to `--color-variable`.
- `--size-bins`, `--size-labels`, `--cmap`, `--color-min`, `--color-max`, `--color-bins`, `--color-labels`.
- `--background land|ocean|plain`, `--coastlines auto|on|off`, `--borders`, and `--gridlines`.
- `--legend-position X Y`, `--legend-fontsize`, `--legend-title-fontsize`, `--tick-fontsize`, and `--colorbar-fontsize` for publication layout tuning.
- `--dpi 300`; never lower for publication figures unless requested.

## Format details

Read [references/formats.md](references/formats.md) when a backend fails, coordinates are projected, HDF paths are ambiguous, or a file contains several variables/groups.

## Outputs

- PNG, PDF, or SVG figure chosen from `--output` extension.
- Sibling `*.stats.json` with input fingerprint, detected format, variable/coordinate names, reductions, data ranges, size encoding, thinning, map settings, warnings, and package versions.

Do not claim that symbol size is proportional to values if a nonlinear transform was used. Do not silently choose among multiple candidate variables, reverse longitude/latitude, reduce dimensions, reproject, aggregate duplicates, or discard more points than the configured cap requires.
