"""Planetary analog search using only data/sites.csv."""
from pathlib import Path
import re
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SITES_PATH = DATA_DIR / "sites.csv"

FEATURES = [
    "temp_mean",
    "temp_range",
    "slope_deg",
    "elevation_m",
    "ice_water_index",
    "aridity_index",
]
FEATURE_LABELS = {
    "temp_mean": "Mean temp",
    "temp_range": "Temp range",
    "slope_deg": "Slope",
    "elevation_m": "Elevation",
    "ice_water_index": "Ice / water",
    "aridity_index": "Aridity",
}
UNITS = {
    "temp_mean": "K",
    "temp_range": "K",
    "slope_deg": "deg",
    "elevation_m": "m",
    "ice_water_index": "",
    "aridity_index": "",
}
DEFAULT_W = {
    "temp_mean": 1.0,
    "temp_range": 1.0,
    "slope_deg": 1.0,
    "elevation_m": 0.5,
    "ice_water_index": 1.0,
    "aridity_index": 1.0,
}
ALIASES = {
    "relief": "elevation_m",
    "elevation_range": "elevation_m",
    "slope": "slope_deg",
    "slope_mean": "slope_deg",
    "roughness": "slope_deg",
    "terrain": "slope_deg",
    "thermal": "temp_mean",
}
KNOWN_KEYWORDS = ("Atacama", "Devon", "Dry Valleys", "Rio Tinto")
BODY_RISKS = {
    "moon": [
        "Gravity is about 1/6 of Earth's",
        "No atmosphere and no magnetic field: high radiation",
        "Abrasive dust and extreme day/night temperature swings",
    ],
    "mars": [
        "Gravity is about 38% of Earth's",
        "Atmosphere is about 0.6% of Earth's pressure and mostly CO2",
        "Higher radiation exposure at the surface",
    ],
}

if not SITES_PATH.exists():
    raise FileNotFoundError(f"sites.csv not found at {SITES_PATH}")

_sites = pd.read_csv(SITES_PATH)
_sites["world"] = _sites["celestial_body"].str.strip().str.lower()
_sites["lat"] = _sites["latitude"].astype(float)
_sites["lon"] = _sites["longitude"].astype(float)
_sites["temp_mean"] = (_sites["min_temp_k"] + _sites["max_temp_k"]) / 2
_sites["temp_range"] = _sites["max_temp_k"] - _sites["min_temp_k"]
_sites["is_known"] = _sites["region_name"].apply(lambda n: any(k in str(n) for k in KNOWN_KEYWORDS))

missing = [c for c in FEATURES if c not in _sites.columns]
if missing:
    raise ValueError(f"sites.csv is missing columns: {missing}")

_X = _sites[FEATURES].astype(float)
_MEAN = _X.mean()
_STD = _X.std().replace(0, 1.0)
_Z = ((_X - _MEAN) / _STD).to_numpy()
_earth_idx = _sites.index[_sites.world == "earth"].to_numpy()


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _split_name(full):
    m = re.match(r"^(.*?)\s*\((.*)\)$", str(full))
    if not m:
        return str(full), ""
    base, inside = m.groups()
    if " - " in inside:
        extra, country = inside.rsplit(" - ", 1)
        return f"{base} ({extra})", country
    return base, inside


def _weight_vector(weights):
    w = dict(DEFAULT_W)
    for k, v in (weights or {}).items():
        key = k if k in w else ALIASES.get(k)
        if not key:
            continue
        try:
            w[key] = max(0.0, float(v))
        except (TypeError, ValueError):
            pass
    return np.array([w[f] for f in FEATURES], dtype=float)


def list_sites(body=None):
    df = _sites
    if body:
        world = str(body).lower()
        df = df[df.world == world]
    out = []
    for _, row in df.iterrows():
        name, country = _split_name(row["region_name"])
        out.append({
            "id": int(row["id"]),
            "body": row["world"],
            "name": name,
            "country": country,
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "note": str(row.get("similarity_reason", "")),
        })
    return out


def find_matches(body, lat, lon, k=5, weights=None, exclude_known=False):
    body = str(body).lower()
    if body == "earth":
        raise ValueError("Choose a point on the Moon or Mars; results are Earth sites.")
    src = _sites[_sites.world == body]
    if src.empty:
        raise ValueError(f"unknown body: {body}")
    if len(_earth_idx) == 0:
        raise ValueError("sites.csv has no Earth rows")

    qi = src.index[_haversine_km(lat, lon, src.lat.to_numpy(), src.lon.to_numpy()).argmin()]
    zq = _Z[qi]
    q_raw = _sites.loc[qi, FEATURES].astype(float)
    click_km = float(_haversine_km(lat, lon, float(_sites.loc[qi, "lat"]), float(_sites.loc[qi, "lon"])))
    confidence = float(1 / (1 + click_km / 400.0))

    w = _weight_vector(weights)
    d = np.sqrt((((_Z[_earth_idx] - zq) * w) ** 2).sum(axis=1))
    if exclude_known:
        d = np.where(_sites.loc[_earth_idx, "is_known"].to_numpy(), np.inf, d)

    order = [j for j in np.argsort(d) if np.isfinite(d[j])][:k]
    out = []
    for rank, j in enumerate(order, 1):
        i = _earth_idx[j]
        row = _sites.loc[i]
        name, country = _split_name(row["region_name"])
        gap = np.abs(_Z[i] - zq)
        dims = {FEATURE_LABELS[f]: float(1 / (1 + gap[n])) for n, f in enumerate(FEATURES)}
        worst = np.argsort(-(gap * w))[:2]
        diffs = []
        for n in worst:
            feat = FEATURES[n]
            unit = UNITS[feat]
            unit_txt = f" {unit}" if unit else ""
            diffs.append(
                f"{FEATURE_LABELS[feat]}: {q_raw.iloc[n]:.0f}{unit_txt} on {body.title()} "
                f"vs {float(row[feat]):.0f}{unit_txt} here"
            )
        out.append({
            "rank": rank,
            "name": name,
            "country": country,
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "similarity": float(1 / (1 + d[j])),
            "confidence": confidence,
            "dimension_scores": dims,
            "risks": BODY_RISKS[body],
            "differences": diffs,
            "is_known": bool(row["is_known"]),
            "note": str(row["similarity_reason"]),
            "matched_from": str(_sites.loc[qi, "region_name"]),
        })
    return out
