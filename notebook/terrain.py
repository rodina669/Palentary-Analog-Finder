"""
terrain.py - ONE function that turns a global DEM into per-cell terrain features.
Use the same function for Earth, Moon and Mars so the numbers are comparable.

Output columns: lat, lon, relief, slope, roughness
  relief    = max - min elevation inside the cell (meters)  -> local, not absolute
  slope     = mean slope in degrees, computed at the DEM's native resolution
  roughness = std of elevation inside the cell (meters)
"""
import warnings
import numpy as np
import pandas as pd

RADIUS_M = {"earth": 6_371_000, "moon": 1_737_400, "mars": 3_389_500}

# Cell size giving roughly the same ground size (~110-120 km) on each body.
# 1 deg is ~111 km on Earth, ~59 km on Mars, ~30 km on the Moon.
CELL_DEG = {"earth": 1.0, "mars": 2.0, "moon": 4.0}


def terrain_cells(dem, body, cell_deg=None, lon_0_360=False):
    """
    dem        : 2D array, global equirectangular, top row = +90 lat, meters, NaN = no data
    body       : "earth" | "moon" | "mars"
    cell_deg   : cell size in degrees (default: CELL_DEG[body])
    lon_0_360  : True if the map's left edge is lon 0 (many PDS files) -> rolled to -180..180
    """
    cell_deg = cell_deg or CELL_DEG[body]
    dem = np.asarray(dem, dtype="float32")
    if lon_0_360:
        dem = np.roll(dem, dem.shape[1] // 2, axis=1)

    H0, W0 = dem.shape
    px_deg = 180.0 / H0                                   # degrees per pixel
    f = int(round(cell_deg / px_deg))                     # pixels per cell side
    H, W = (H0 // f) * f, (W0 // f) * f

    # slope at native resolution, in real meters on that body
    m = np.deg2rad(px_deg) * RADIUS_M[body]
    lat_px = 90 - px_deg * (np.arange(H0) + 0.5)
    cosl = np.clip(np.cos(np.deg2rad(lat_px)), 0.05, None)[:, None]
    dy = np.gradient(dem, axis=0) / m
    dx = np.gradient(dem, axis=1) / (m * cosl)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))

    blk = lambda a: a[:H, :W].reshape(H // f, f, W // f, f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        d = blk(dem)
        relief = np.nanmax(d, axis=(1, 3)) - np.nanmin(d, axis=(1, 3))
        rough = np.nanstd(d, axis=(1, 3))
        slope_m = np.nanmean(blk(slope), axis=(1, 3))

    n_lat, n_lon = H // f, W // f
    lat = 90 - cell_deg * (np.arange(n_lat) + 0.5)
    lon = -180 + cell_deg * (np.arange(n_lon) + 0.5)
    LON, LAT = np.meshgrid(lon, lat)
    return pd.DataFrame({
        "lat": LAT.ravel(), "lon": LON.ravel(),
        "relief": relief.ravel(), "slope": slope_m.ravel(), "roughness": rough.ravel(),
    }).dropna()
