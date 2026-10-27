"""Explore Sentinel-5P TROPOMI methane (XCH4) over a region with the Earth Engine Python API.

Usage:
    EE_PROJECT=<your-cloud-project-id> python src/explore_xch4.py

Writes to outputs/:
    xch4_anomaly.png   mean XCH4 over the period, as a difference from the regional median
    xch4_monthly.csv   monthly regional mean XCH4 and how many valid retrievals went into it
    xch4_monthly.png   time-series chart of the CSV

The Earth Engine calls live in main() and the two fetch_* functions. Everything else is
plain Python so it can be unit-tested without an Earth Engine account.
"""

import os
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

BBOX = (52.5, 37.5, 55.5, 40.5)  # west, south, east, north: western Turkmenistan, a known methane hotspot
START, END = "2023-01-01", "2026-01-01"  # END is exclusive
COLLECTION = "COPERNICUS/S5P/OFFL/L3_CH4"
BAND = "CH4_column_volume_mixing_ratio_dry_air"  # ppb
SCALE = 7000  # metres, close to TROPOMI's native resolution
GRID_STEP = 0.05  # degrees, ~4-5.5 km here: the map grid, no finer than the data supports
MAP_LIMIT = 20  # ppb, colour scale runs from -MAP_LIMIT to +MAP_LIMIT
NO_DATA = -9999
OUT_DIR = Path("outputs")

# Reference points to help orient the map, (lon, lat)
PLACES = {"Turkmenbashi": (52.96, 40.02), "Balkanabat": (54.37, 39.51)}

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"
SERIES = "#2a78d6"
DIVERGING = LinearSegmentedColormap.from_list("xch4_anomaly", ["#2a78d6", "#f0efec", "#e34948"])


# --- Pure logic (no Earth Engine) -------------------------------------------------------


def month_starts(start: str, end: str) -> list[str]:
    """First day of each whole month from start up to, but not including, end."""
    return pd.date_range(start, end, freq="MS", inclusive="left").strftime("%Y-%m-%d").tolist()


def anomaly(values) -> np.ndarray:
    """Difference of each value from the median of all values, ignoring NaN gaps."""
    values = np.asarray(values, dtype=float)
    return values - np.nanmedian(values)


def build_dataframe(features: list[dict]) -> pd.DataFrame:
    """Turn the monthly features from Earth Engine into a dataframe sorted by month.

    A month with no valid retrievals comes back without an XCH4 value. It is kept as NaN
    rather than dropped, so the gap stays visible in the CSV and the chart.
    """
    rows = [f["properties"] for f in features]
    df = pd.DataFrame(rows, columns=["month", "xch4_ppb", "obs_per_pixel"])
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m")
    df["xch4_ppb"] = pd.to_numeric(df["xch4_ppb"]).round(2)
    df["obs_per_pixel"] = pd.to_numeric(df["obs_per_pixel"]).fillna(0).round(2)
    return df.sort_values("month").reset_index(drop=True)


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelcolor=MUTED, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")


def plot_monthly(df: pd.DataFrame, path: Path) -> None:
    """Monthly regional mean XCH4, with the number of valid retrievals per pixel below it."""
    months = pd.to_datetime(df["month"])
    fig = Figure(figsize=(9, 5.5), facecolor=SURFACE, layout="constrained")
    top, bottom = fig.subplots(2, 1, sharex=True, height_ratios=[3, 1])

    _style(top)
    top.plot(
        months,
        df["xch4_ppb"],
        color=SERIES,
        linewidth=1.5,
        marker="o",
        markersize=5,
        markeredgecolor=SURFACE,
        markeredgewidth=1.5,
    )
    median = np.nanmedian(df["xch4_ppb"])
    top.axhline(median, color=MUTED, linewidth=1)
    top.annotate(
        f"median {median:.0f} ppb",
        (months.iloc[0], median),
        xytext=(0, 5),
        textcoords="offset points",
        color=MUTED,
        fontsize=9,
    )
    top.set_ylabel("XCH4 (ppb)", color=MUTED)
    top.set_title(
        "Monthly mean XCH4 over western Turkmenistan, Sentinel-5P TROPOMI", loc="left", color=INK, fontsize=12
    )

    _style(bottom)
    bottom.bar(months, df["obs_per_pixel"], width=20, color="#9ec5f4")
    bottom.set_ylabel("Valid retrievals\nper pixel", color=MUTED)
    bottom.yaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))

    fig.savefig(path, dpi=150)


def plot_anomaly(grid: np.ndarray, bbox: tuple, path: Path, places: dict | None = None) -> None:
    """Map of the XCH4 anomaly grid (ppb, NaN where there is no data) over bbox."""
    west, south, east, north = bbox
    fig = Figure(figsize=(7, 6.2), facecolor=SURFACE, layout="constrained")
    ax = fig.subplots()
    ax.set_facecolor(SURFACE)
    # Hatching shows through wherever the grid is NaN: no valid retrievals
    ax.add_patch(
        Rectangle(
            (west, south),
            east - west,
            north - south,
            fill=False,
            hatch="////",
            edgecolor="#c3c2b7",
            linewidth=0,
            zorder=0,
        )
    )
    cmap = DIVERGING.with_extremes(bad=(0, 0, 0, 0))
    image = ax.imshow(
        np.ma.masked_invalid(grid),
        extent=(west, east, south, north),
        origin="upper",
        cmap=cmap,
        vmin=-MAP_LIMIT,
        vmax=MAP_LIMIT,
        interpolation="nearest",
        zorder=1,
    )
    for name, (lon, lat) in (places or {}).items():
        ax.plot(lon, lat, "o", color=INK, markersize=4, zorder=2)
        ax.annotate(
            name, (lon, lat), xytext=(5, 4), textcoords="offset points", color=INK, fontsize=9, zorder=2
        )
    bar = fig.colorbar(image, ax=ax, extend="both", shrink=0.8)
    bar.set_label("XCH4 minus regional median (ppb)", color=MUTED)
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=MUTED, length=0)
    ax.set_xlabel("Longitude (°E)", color=MUTED)
    ax.set_ylabel("Latitude (°N)", color=MUTED)
    ax.tick_params(colors=MUTED, labelcolor=MUTED)
    for spine in ax.spines.values():
        spine.set_color("#c3c2b7")
    ax.set_title(
        f"Mean XCH4 anomaly, {START[:7]} to {END[:7]} (hatched = no data)", loc="left", color=INK, fontsize=11
    )
    fig.savefig(path, dpi=150)


# --- Earth Engine -----------------------------------------------------------------------


def fetch_mean_grid(col: ee.ImageCollection, bbox: tuple, step: float) -> np.ndarray:
    """Mean XCH4 over the whole collection, sampled onto a regular lon/lat grid."""
    west, south, east, north = bbox
    grid = {
        "dimensions": {"width": round((east - west) / step), "height": round((north - south) / step)},
        "affineTransform": {
            "scaleX": step,
            "shearX": 0,
            "translateX": west,
            "shearY": 0,
            "scaleY": -step,
            "translateY": north,
        },
        "crsCode": "EPSG:4326",
    }
    pixels = ee.data.computePixels(
        {
            "expression": col.mean().unmask(NO_DATA),
            "fileFormat": "NUMPY_NDARRAY",
            "grid": grid,
        }
    )
    values = pixels[BAND].astype(float)
    values[values == NO_DATA] = np.nan
    return values


def fetch_monthly(col: ee.ImageCollection, region: ee.Geometry, months: list[str]) -> list[dict]:
    """Regional mean XCH4 and mean valid retrievals per pixel, for each month."""

    def monthly(m):
        start = ee.Date(m)
        month_col = col.filterDate(start, start.advance(1, "month"))
        mean = month_col.mean().reduceRegion(ee.Reducer.mean(), region, SCALE, maxPixels=1e9)
        count = month_col.count().unmask(0).reduceRegion(ee.Reducer.mean(), region, SCALE, maxPixels=1e9)
        return ee.Feature(None, {"month": m, "xch4_ppb": mean.get(BAND), "obs_per_pixel": count.get(BAND)})

    return ee.FeatureCollection(ee.List(months).map(monthly)).getInfo()["features"]


def main() -> None:
    project = os.environ.get("EE_PROJECT")
    if not project:
        sys.exit("Set EE_PROJECT to a Google Cloud project ID registered for Earth Engine.")
    ee.Initialize(project=project)

    region = ee.Geometry.Rectangle(list(BBOX))
    col = ee.ImageCollection(COLLECTION).select(BAND).filterDate(START, END).filterBounds(region)
    OUT_DIR.mkdir(exist_ok=True)

    # 1. Mean XCH4 map as an anomaly against the regional median
    grid = anomaly(fetch_mean_grid(col, BBOX, GRID_STEP))
    plot_anomaly(grid, BBOX, OUT_DIR / "xch4_anomaly.png", PLACES)

    # 2. Monthly regional mean time series
    df = build_dataframe(fetch_monthly(col, region, month_starts(START, END)))
    df.to_csv(OUT_DIR / "xch4_monthly.csv", index=False)
    plot_monthly(df, OUT_DIR / "xch4_monthly.png")
    print(df.tail())


if __name__ == "__main__":
    main()
