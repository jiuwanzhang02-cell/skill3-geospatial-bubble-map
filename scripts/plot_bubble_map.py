#!/usr/bin/env python3
"""Create proportional-symbol maps from point tables or geoscience grids."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import warnings
from pathlib import Path

import numpy as np

LAT_ALIASES = ("lat", "latitude", "nav_lat", "y")
LON_ALIASES = ("lon", "longitude", "nav_lon", "x")
TABLE_EXT = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
RASTER_EXT = {".tif", ".tiff"}
GRIB_EXT = {".grib", ".grb", ".grib2", ".grb2"}
HDF_EXT = {".h5", ".hdf5", ".he5", ".hdf"}
NETCDF_EXT = {".nc", ".nc4", ".cdf"}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--input-format", choices=["table", "netcdf", "zarr", "geotiff", "hdf5", "grib"])
    p.add_argument("--size-variable", required=True)
    p.add_argument("--color-variable")
    p.add_argument("--lat-name")
    p.add_argument("--lon-name")
    p.add_argument("--sheet-name", default=0)
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--select", action="append", default=[], metavar="DIM=INDEX")
    p.add_argument("--reduce", choices=["first", "mean", "sum", "max", "min"])
    p.add_argument("--aggregate", choices=["mean", "sum", "max"])
    p.add_argument("--allow-reproject", action="store_true")
    p.add_argument("--absolute-size", action="store_true")
    p.add_argument("--keep-zero", action="store_true")
    p.add_argument("--max-points", type=int, default=50000)
    p.add_argument("--size-transform", choices=["linear", "sqrt", "log1p"], default="linear")
    p.add_argument("--min-area", type=float, default=12.0)
    p.add_argument("--max-area", type=float, default=420.0)
    p.add_argument("--size-breaks", type=float, nargs="+")
    p.add_argument("--size-bins", type=float, nargs="+", help="Increasing class edges; marker area is constant within each interval")
    p.add_argument("--size-labels", nargs="+", help="Labels for --size-bins intervals")
    p.add_argument("--color-bins", type=float, nargs="+")
    p.add_argument("--color-labels", nargs="+")
    p.add_argument("--color-min", type=float)
    p.add_argument("--color-max", type=float)
    p.add_argument("--cmap", default="viridis")
    p.add_argument("--single-color", default="#5b4ab3")
    p.add_argument("--alpha", type=float, default=0.78)
    p.add_argument("--edge-color", default="#333333")
    p.add_argument("--edge-width", type=float, default=0.35)
    p.add_argument("--projection", choices=["platecarree", "robinson", "equalearth", "mollweide", "mercator"], default="platecarree")
    p.add_argument("--global", dest="global_map", action="store_true")
    p.add_argument("--extent", type=float, nargs=4, metavar=("W", "E", "S", "N"))
    p.add_argument("--central-longitude", type=float, default=0.0)
    p.add_argument("--background", choices=["land", "ocean", "plain"], default="land")
    p.add_argument("--coastlines", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--borders", action="store_true")
    p.add_argument("--gridlines", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--title", default="Geospatial bubble map")
    p.add_argument("--size-label")
    p.add_argument("--color-label")
    p.add_argument("--size-unit", default="")
    p.add_argument("--color-unit", default="")
    p.add_argument("--legend-position", type=float, nargs=2, default=(0.02, 0.03), metavar=("X", "Y"),
                   help="Size-legend lower-left anchor in map-axes coordinates")
    p.add_argument("--legend-fontsize", type=float, default=10.0)
    p.add_argument("--legend-title-fontsize", type=float, default=11.0)
    p.add_argument("--tick-fontsize", type=float, default=10.0, help="Longitude/latitude label size")
    p.add_argument("--colorbar-fontsize", type=float, default=10.0)
    p.add_argument("--figsize", type=float, nargs=2, default=(12.0, 7.0))
    p.add_argument("--dpi", type=int, default=300)
    return p


def detect_format(path, explicit=None):
    if explicit:
        return explicit
    if path.is_dir() and path.suffix.lower() == ".zarr":
        return "zarr"
    ext = path.suffix.lower()
    if ext in TABLE_EXT: return "table"
    if ext in RASTER_EXT: return "geotiff"
    if ext in GRIB_EXT: return "grib"
    if ext in HDF_EXT: return "hdf5"
    if ext in NETCDF_EXT: return "netcdf"
    raise ValueError(f"Cannot detect format from {path}; use --input-format")


def find_name(names, requested, aliases, role):
    names = list(names)
    if requested:
        if requested in names: return requested
        matches = [n for n in names if n.split("/")[-1] == requested]
        if len(matches) == 1: return matches[0]
        raise ValueError(f"{role} {requested!r} not found; available: {names}")
    low = {str(n).lower(): n for n in names}
    matches = [low[a] for a in aliases if a in low]
    if len(matches) == 1: return matches[0]
    if not matches: raise ValueError(f"Could not detect {role}; use --{role.replace(' ', '-')}-name")
    raise ValueError(f"Ambiguous {role}: {matches}; specify it")


def parse_select(items):
    out = {}
    for item in items:
        if "=" not in item: raise ValueError(f"Expected DIM=INDEX, got {item!r}")
        dim, value = item.split("=", 1)
        out[dim] = int(value)
    return out


def load_table(args, notes):
    import pandas as pd
    ext = args.input.suffix.lower()
    if ext in {".xlsx", ".xls"}:
        sheet = int(args.sheet_name) if str(args.sheet_name).isdigit() else args.sheet_name
        df = pd.read_excel(args.input, sheet_name=sheet)
    elif ext == ".tsv":
        df = pd.read_csv(args.input, sep="\t")
    else:
        df = pd.read_csv(args.input, sep=None, engine="python")
    lon_name = find_name(df.columns, args.lon_name, LON_ALIASES, "lon")
    lat_name = find_name(df.columns, args.lat_name, LAT_ALIASES, "lat")
    needed = [lon_name, lat_name, args.size_variable] + ([args.color_variable] if args.color_variable else [])
    missing = [x for x in needed if x not in df.columns]
    if missing: raise ValueError(f"Columns not found: {missing}; available: {list(df.columns)}")
    if args.aggregate:
        funcs = {args.size_variable: args.aggregate}
        if args.color_variable: funcs[args.color_variable] = args.aggregate
        df = df.groupby([lon_name, lat_name], as_index=False).agg(funcs)
        notes.append(f"duplicate coordinates aggregated with {args.aggregate}")
    return (df[lon_name].to_numpy(float), df[lat_name].to_numpy(float),
            df[args.size_variable].to_numpy(float),
            df[args.color_variable].to_numpy(float) if args.color_variable else None,
            lon_name, lat_name, {})


def apply_selection_and_reduction(da, spatial_dims, args, reductions):
    selectors = parse_select(args.select)
    unknown = set(selectors) - set(da.dims)
    if unknown: raise ValueError(f"Selection dimensions absent from {da.name}: {sorted(unknown)}")
    if selectors:
        da = da.isel(selectors)
        reductions.append({"select": selectors})
    extra = [d for d in da.dims if d not in spatial_dims]
    if extra:
        if not args.reduce:
            raise ValueError(f"Variable {da.name!r} has extra dimensions {extra}; use --select or --reduce")
        if args.reduce == "first": da = da.isel({d: 0 for d in extra})
        else: da = getattr(da, args.reduce)(dim=extra, skipna=True)
        reductions.append({"method": args.reduce, "dimensions": extra})
    return da.squeeze(drop=True)


def load_xarray(args, fmt, notes):
    import xarray as xr
    kwargs = {"engine": "cfgrib"} if fmt == "grib" else {}
    ds = xr.open_zarr(args.input) if fmt == "zarr" else xr.open_dataset(args.input, **kwargs)
    all_names = list(ds.coords) + [d for d in ds.dims if d not in ds.coords] + list(ds.data_vars)
    lon_name = find_name(all_names, args.lon_name, LON_ALIASES, "lon")
    lat_name = find_name(all_names, args.lat_name, LAT_ALIASES, "lat")
    for name in [args.size_variable] + ([args.color_variable] if args.color_variable else []):
        if name not in ds: raise ValueError(f"Variable {name!r} absent; available: {list(ds.data_vars)}")
    lon = ds[lon_name]; lat = ds[lat_name]
    spatial_dims = set(lon.dims) | set(lat.dims)
    reductions = []
    size = apply_selection_and_reduction(ds[args.size_variable], spatial_dims, args, reductions)
    color = apply_selection_and_reduction(ds[args.color_variable], spatial_dims, args, reductions) if args.color_variable else None
    lon, lat, size = xr.broadcast(lon, lat, size)
    if color is not None:
        _, _, color = xr.broadcast(lon, lat, color)
    return (lon.values.ravel(), lat.values.ravel(), size.values.ravel(),
            color.values.ravel() if color is not None else None,
            lon_name, lat_name, {"reductions": reductions, "dimensions": dict(ds.sizes)})


def load_geotiff(args, notes):
    import rasterio
    from rasterio.transform import xy
    with rasterio.open(args.input) as src:
        if not 1 <= args.band <= src.count: raise ValueError(f"Band must be 1..{src.count}")
        data = src.read(args.band, masked=True).filled(np.nan).astype(float)
        rows, cols = np.indices(data.shape)
        xs, ys = xy(src.transform, rows, cols, offset="center")
        lon, lat = np.asarray(xs), np.asarray(ys)
        crs = src.crs
        if crs and not crs.is_geographic:
            if not args.allow_reproject: raise ValueError(f"GeoTIFF CRS {crs} is projected; use --allow-reproject")
            from rasterio.warp import transform
            lon1, lat1 = transform(crs, "EPSG:4326", lon.ravel(), lat.ravel())
            lon, lat = np.asarray(lon1).reshape(data.shape), np.asarray(lat1).reshape(data.shape)
            notes.append(f"pixel centers transformed from {crs} to EPSG:4326")
        if args.color_variable:
            try: color_band = int(args.color_variable)
            except ValueError as exc: raise ValueError("For GeoTIFF, --color-variable must be a 1-based band number") from exc
            color = src.read(color_band, masked=True).filled(np.nan).astype(float)
        else: color = None
        meta = {"crs": str(crs), "shape": list(data.shape), "band": args.band}
    return lon.ravel(), lat.ravel(), data.ravel(), color.ravel() if color is not None else None, "x", "y", meta


def load_hdf5(args, notes):
    try:
        return load_xarray(args, "hdf5", notes)
    except Exception as first:
        notes.append(f"xarray HDF open failed; used h5py: {type(first).__name__}")
    import h5py
    arrays = {}
    with h5py.File(args.input, "r") as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset) and np.issubdtype(obj.dtype, np.number): arrays[name] = obj[...]
        f.visititems(visit)
    names = list(arrays)
    lon_name = find_name(names, args.lon_name, LON_ALIASES, "lon")
    lat_name = find_name(names, args.lat_name, LAT_ALIASES, "lat")
    size_name = find_name(names, args.size_variable, (), "size variable")
    color_name = find_name(names, args.color_variable, (), "color variable") if args.color_variable else None
    lon, lat, size = arrays[lon_name], arrays[lat_name], arrays[size_name]
    if lon.ndim == lat.ndim == 1 and size.ndim == 2: lon, lat = np.meshgrid(lon, lat)
    if lon.shape != size.shape or lat.shape != size.shape: raise ValueError("HDF coordinate and science-field shapes do not match")
    color = arrays[color_name] if color_name else None
    if color is not None and color.shape != size.shape: raise ValueError("HDF color-field shape does not match size field")
    return lon.ravel(), lat.ravel(), size.ravel(), color.ravel() if color is not None else None, lon_name, lat_name, {"datasets": names}


def load_data(args, fmt, notes):
    if fmt == "table": return load_table(args, notes)
    if fmt == "geotiff": return load_geotiff(args, notes)
    if fmt == "hdf5": return load_hdf5(args, notes)
    return load_xarray(args, fmt, notes)


def normalize_lon(lon, notes):
    if np.nanmax(lon) > 180 and np.nanmin(lon) >= 0:
        lon = ((lon + 180) % 360) - 180
        notes.append("longitude normalized from 0–360 to −180–180")
    return lon


def clean_and_thin(lon, lat, size, color, args, notes):
    lon, lat, size = map(lambda x: np.asarray(x, dtype=float).ravel(), (lon, lat, size))
    color = np.asarray(color, dtype=float).ravel() if color is not None else None
    if not (len(lon) == len(lat) == len(size)) or (color is not None and len(color) != len(size)):
        raise ValueError("Coordinate and variable arrays have different lengths")
    lon = normalize_lon(lon, notes)
    mask = np.isfinite(lon) & np.isfinite(lat) & np.isfinite(size) & (lat >= -90) & (lat <= 90)
    if color is not None: mask &= np.isfinite(color)
    if args.absolute_size:
        size = np.abs(size); notes.append("absolute value used for marker size")
    elif np.any(size[mask] < 0):
        raise ValueError("Negative size values found; use --absolute-size only if magnitude is intended")
    if not args.keep_zero: mask &= size > 0
    lon, lat, size = lon[mask], lat[mask], size[mask]
    if color is not None: color = color[mask]
    before = len(size)
    stride = 1
    if before > args.max_points:
        stride = math.ceil(before / args.max_points)
        idx = np.arange(0, before, stride)
        extreme = int(np.nanargmax(size))
        idx = np.unique(np.append(idx, extreme))[:args.max_points]
        lon, lat, size = lon[idx], lat[idx], size[idx]
        if color is not None: color = color[idx]
        notes.append(f"deterministic stride {stride} retained {len(size)} of {before} points")
    if not len(size): raise ValueError("No finite positive points remain after filtering")
    return lon, lat, size, color, before, stride


def transform_values(values, kind):
    if kind == "linear": return values
    if kind == "sqrt": return np.sqrt(values)
    return np.log1p(values)


def marker_areas(values, args):
    transformed = transform_values(values, args.size_transform)
    hi = float(np.nanmax(transformed))
    if hi == 0: return np.full_like(transformed, args.min_area)
    return np.maximum(args.min_area, args.max_area * transformed / hi)


def representative_breaks(values, supplied):
    if supplied: return np.asarray(supplied, float)
    vals = np.unique(np.nanquantile(values, [0.25, 0.5, 0.75, 1.0]))
    return vals[vals > 0]


def classified_areas(values, args):
    edges = np.asarray(args.size_bins, float)
    if len(edges) < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError("--size-bins must contain at least two increasing edges")
    if np.nanmin(values) < edges[0] or np.nanmax(values) > edges[-1]:
        raise ValueError(f"--size-bins must cover the data range {np.nanmin(values):g}..{np.nanmax(values):g}")
    n = len(edges) - 1
    class_areas = np.linspace(args.min_area, args.max_area, n)
    classes = np.digitize(values, edges[1:-1], right=False)
    labels = args.size_labels
    if labels and len(labels) != n:
        raise ValueError("--size-labels count must equal number of size intervals")
    if not labels:
        labels = [f"{edges[i]:g}–{edges[i+1]:g}" for i in range(n)]
    return class_areas[classes], class_areas, labels, edges


def projection(args, ccrs):
    kw = {"central_longitude": args.central_longitude}
    return {"platecarree": ccrs.PlateCarree, "robinson": ccrs.Robinson,
            "equalearth": ccrs.EqualEarth, "mollweide": ccrs.Mollweide,
            "mercator": ccrs.Mercator}[args.projection](**kw)


def natural_earth_cached(cartopy, category, name, resolution="110m"):
    roots = [cartopy.config.get("data_dir"), cartopy.config.get("pre_existing_data_dir"),
             cartopy.config.get("repo_data_dir")]
    return any(root and (Path(root) / "shapefiles" / "natural_earth" / category /
                         f"ne_{resolution}_{name}.shp").exists() for root in roots)


def infer_extent(lon, lat):
    w, e, s, n = map(float, (np.nanmin(lon), np.nanmax(lon), np.nanmin(lat), np.nanmax(lat)))
    dx, dy = max((e-w)*0.06, 1), max((n-s)*0.08, 1)
    return [max(-180, w-dx), min(180, e+dx), max(-90, s-dy), min(90, n+dy)]


def plot(args, lon, lat, size, color, notes):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(os.getenv("TMPDIR", "/tmp")) / "bubble-map-mpl"))
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes
    import cartopy
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    fig = plt.figure(figsize=args.figsize)
    ax = fig.add_subplot(1, 1, 1, projection=projection(args, ccrs))
    ax.set_facecolor("#edf3f7" if args.background == "ocean" else "white")
    land_cached = natural_earth_cached(cartopy, "physical", "land")
    if args.background in {"land", "ocean"} and land_cached:
        face = "#f1f1ee" if args.background == "land" else "#f5f5f1"
        ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor=face, zorder=0)
    elif args.background in {"land", "ocean"}:
        notes.append("land polygons skipped because Natural Earth vectors were not cached")

    coast_cached = natural_earth_cached(cartopy, "physical", "coastline")
    coast = args.coastlines == "on" or (args.coastlines == "auto" and coast_cached)
    if coast: ax.coastlines("110m", color="#555555", linewidth=0.55, zorder=2)
    elif args.coastlines == "auto": notes.append("coastlines skipped because Natural Earth vectors were not cached")
    if args.borders:
        if natural_earth_cached(cartopy, "cultural", "admin_0_boundary_lines_land"):
            ax.add_feature(cfeature.BORDERS.with_scale("110m"), edgecolor="#777777", linewidth=0.35)
        else: notes.append("borders skipped because Natural Earth vectors were not cached")
    if args.global_map: ax.set_global(); extent = [-180, 180, -90, 90]
    else:
        extent = args.extent or infer_extent(lon, lat)
        ax.set_extent(extent, crs=ccrs.PlateCarree())
    if args.gridlines:
        gl = ax.gridlines(draw_labels=args.projection == "platecarree", linewidth=0.35, color="#999999", alpha=0.5, linestyle="--")
        if args.projection == "platecarree": gl.top_labels = False; gl.right_labels = False
        gl.xlabel_style = {"size": args.tick_fontsize}
        gl.ylabel_style = {"size": args.tick_fontsize}

    if args.size_bins:
        areas, legend_areas, labels, size_edges = classified_areas(size, args)
        breaks = None
    else:
        areas = marker_areas(size, args)
        breaks = representative_breaks(size, args.size_breaks)
        legend_areas = [float(marker_areas(np.asarray([v, np.nanmax(size)]), args)[0]) for v in breaks]
        labels = [f"{v:.3g}" + (f" {args.size_unit}" if args.size_unit else "") for v in breaks]
        size_edges = None
    scatter_kw = dict(s=areas, alpha=args.alpha, edgecolors=args.edge_color, linewidths=args.edge_width,
                      transform=ccrs.PlateCarree(), zorder=3)
    norm = None
    if color is None:
        sc = ax.scatter(lon, lat, color=args.single_color, **scatter_kw)
    else:
        if args.color_bins:
            edges = np.asarray(args.color_bins, float)
            if len(edges) < 2 or np.any(np.diff(edges) <= 0): raise ValueError("--color-bins must contain increasing edges")
            norm = mcolors.BoundaryNorm(edges, plt.get_cmap(args.cmap).N, clip=True)
        else:
            norm = mcolors.Normalize(vmin=args.color_min, vmax=args.color_max)
        sc = ax.scatter(lon, lat, c=color, cmap=args.cmap, norm=norm, **scatter_kw)
        cax = inset_axes(ax, width="2.8%", height="100%", loc="lower left",
                         bbox_to_anchor=(1.035, 0, 1, 1), bbox_transform=ax.transAxes,
                         borderpad=0)
        cb = fig.colorbar(sc, cax=cax, boundaries=args.color_bins or None)
        cb.set_label(args.color_label or args.color_variable + (f" ({args.color_unit})" if args.color_unit else ""))
        cb.ax.tick_params(labelsize=args.colorbar_fontsize)
        cb.ax.yaxis.label.set_size(args.colorbar_fontsize)
        if args.color_labels:
            if not args.color_bins or len(args.color_labels) != len(args.color_bins)-1:
                raise ValueError("--color-labels count must equal number of color intervals")
            mids = [(a+b)/2 for a,b in zip(args.color_bins[:-1], args.color_bins[1:])]
            cb.set_ticks(mids); cb.set_ticklabels(args.color_labels)

    handles = [plt.scatter([], [], s=float(area), facecolors="none", edgecolors=args.edge_color,
                           linewidths=0.7) for area in legend_areas]
    legend = ax.legend(handles, labels, title=args.size_label or args.size_variable, loc="lower left",
                       bbox_to_anchor=args.legend_position, bbox_transform=ax.transAxes,
                       frameon=True, framealpha=0.9, labelspacing=1.1, borderpad=0.8,
                       fontsize=args.legend_fontsize)
    legend.get_title().set_fontsize(args.legend_title_fontsize)
    ax.set_title(args.title, fontsize=14, pad=12)
    fig.tight_layout()
    return fig, areas, extent, size_edges


def file_hash(path):
    if path.is_dir(): return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    args = parser().parse_args(argv)
    if not args.input.exists(): raise FileNotFoundError(args.input)
    if args.max_points < 1 or args.min_area <= 0 or args.max_area < args.min_area: raise ValueError("Invalid point or marker-area limits")
    if args.size_breaks and args.size_bins: raise ValueError("Use either --size-breaks or --size-bins, not both")
    if args.size_labels and not args.size_bins: raise ValueError("--size-labels requires --size-bins")
    fmt = detect_format(args.input, args.input_format)
    args.output = args.output or args.input.with_name(args.input.stem + "_bubble_map.png")
    if args.output.suffix.lower() not in {".png", ".pdf", ".svg"}: raise ValueError("Output must be PNG, PDF, or SVG")
    notes = []
    lon, lat, size, color, lon_name, lat_name, source_meta = load_data(args, fmt, notes)
    lon, lat, size, color, valid_before_thin, stride = clean_and_thin(lon, lat, size, color, args, notes)
    fig, areas, extent, size_edges = plot(args, lon, lat, size, color, notes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=args.dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt; plt.close(fig)
    stats = {
        "input": str(args.input.resolve()), "input_sha256": file_hash(args.input), "format": fmt,
        "output": str(args.output.resolve()), "coordinates": {"longitude": lon_name, "latitude": lat_name},
        "variables": {"size": args.size_variable, "color": args.color_variable}, "source": source_meta,
        "points": {"valid_before_thinning": valid_before_thin, "plotted": len(size), "stride": stride, "max_points": args.max_points},
        "size_encoding": {"transform": "classified" if args.size_bins else args.size_transform,
                          "bins": None if size_edges is None else size_edges.tolist(),
                          "labels": args.size_labels,
                          "area_range_points2": [args.min_area, args.max_area],
                          "value_min": float(np.min(size)), "value_max": float(np.max(size)),
                          "area_proportional_above_minimum_clip": not args.size_bins and args.size_transform == "linear",
                          "minimum_area_clipping": bool(np.max(transform_values(size, args.size_transform)) > 0 and
                                                        np.any(args.max_area * transform_values(size, args.size_transform) /
                                                               np.max(transform_values(size, args.size_transform)) < args.min_area))},
        "color_range": None if color is None else [float(np.min(color)), float(np.max(color))],
        "map": {"projection": args.projection, "central_longitude": args.central_longitude, "extent": extent, "dpi": args.dpi,
                "legend_position": list(args.legend_position), "tick_fontsize": args.tick_fontsize,
                "colorbar_fontsize": args.colorbar_fontsize},
        "notes": notes, "versions": {"python": sys.version.split()[0], "numpy": np.__version__},
    }
    stats_path = args.output.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"figure": str(args.output), "stats": str(stats_path), "points": len(size), "notes": notes}, ensure_ascii=False))


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
