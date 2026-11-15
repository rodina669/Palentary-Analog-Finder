import os
import numpy as np
import pandas as pd

CELL = 2
rng = np.random.default_rng(42)

lats = 90 - (np.arange(180 // CELL) + 0.5) * CELL
lons = -180 + (np.arange(360 // CELL) + 0.5) * CELL
LON, LAT = np.meshgrid(lons, lats)
LAT, LON = LAT.ravel(), LON.ravel()
n = LAT.size

PROFILE = {
    "earth": (1500, 8, 300, 15, 30),
    "moon": (2500, 6, 450, -50, 280),
    "mars": (3000, 9, 600, -60, 100),
}

frames = []
for world, (rel, slp, rough, tm, tr) in PROFILE.items():
    frames.append(pd.DataFrame({
        "world": world, "lat": LAT, "lon": LON,
        "relief": rng.gamma(2.0, rel / 2, n),
        "slope": rng.gamma(2.0, slp / 2, n),
        "roughness": rng.gamma(2.0, rough / 2, n),
        "temp_mean": tm - 0.4 * np.abs(LAT) + rng.normal(0, 3, n),
        "temp_range": tr + rng.normal(0, 5, n),
    }))

grid = pd.concat(frames, ignore_index=True)
keep = rng.random(len(grid)) < 0.33
grid = grid[(grid.world != "earth") | keep].reset_index(drop=True)

os.makedirs("data", exist_ok=True)
grid.to_csv("data/grid.csv", index=False)
print(grid.groupby("world").size())
print("done: data/grid.csv")