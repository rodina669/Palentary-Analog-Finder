"""
matcher.py (نسخة sites.csv فقط)
بتشتغل على 25 موقع مرجعي بدل شبكة كاملة. نفس الشكل اللي server.py والـ 3D متوقعينه.

القاعدة:
  1) الضغطة على القمر/المريخ بتتحوّل لأقرب موقع مرجعي على نفس الجرم.
  2) بنقارن خصائصه بمواقع الأرض، ونرجّع أقرب k.
"""
import re
import numpy as np
import pandas as pd

SITES_PATH = "data/sites.csv"
MIN_SEPARATION_KM = 0  # المواقع قليلة ومتباعدة، فمفيش داعي لفلترة الجيران

# اسم الخاصية في الملف -> (الاسم اللي بنعرضه، الوحدة)
FEATURES = ["temp_mean", "temp_range", "slope_deg", "elevation_m",
            "ice_water_index", "aridity_index"]
UNITS = {"temp_mean": "K", "temp_range": "K", "slope_deg": "deg", "elevation_m": "m",
         "ice_water_index": "", "aridity_index": ""}
# الوزن الافتراضي: الارتفاع أقل أهمية لأنه مقاس من مراجع مختلفة بين الأجرام
DEFAULT_W = {"temp_mean": 1.0, "temp_range": 1.0, "slope_deg": 1.0, "elevation_m": 0.5,
             "ice_water_index": 1.0, "aridity_index": 1.0}
# أسماء الأوزان اللي ممكن الواجهة تبعتها -> الخاصية المناسبة هنا
ALIASES = {"relief": "elevation_m", "elevation_range": "elevation_m", "slope": "slope_deg",
           "slope_mean": "slope_deg", "roughness": "slope_deg"}

# مواقع الأرض المعروفة كمواقع تناظر قديمة (تُستبعد لو exclude_known=True)
KNOWN_KEYWORDS = ("Atacama", "Devon", "Dry Valleys", "Rio Tinto")

BODY_RISKS = {
    "moon": ["Gravity is about 1/6 of Earth's", "No atmosphere and no magnetic field: high radiation",
             "Abrasive dust and extreme day/night temperature swings"],
    "mars": ["Gravity is about 38% of Earth's", "Atmosphere is about 0.6% of Earth's pressure and mostly CO2",
             "Higher radiation exposure at the surface"],
}

# ---------------------------------------------------------------- تحميل البيانات
_sites = pd.read_csv(SITES_PATH)
_sites["world"] = _sites["celestial_body"].str.strip().str.lower()
_sites["lat"] = _sites["latitude"].astype(float)
_sites["lon"] = _sites["longitude"].astype(float)
_sites["temp_mean"] = (_sites["min_temp_k"] + _sites["max_temp_k"]) / 2
_sites["temp_range"] = _sites["max_temp_k"] - _sites["min_temp_k"]
_sites["is_known"] = _sites["region_name"].apply(lambda n: any(k in n for k in KNOWN_KEYWORDS))

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
    """'Atacama Desert (Yungay - Chile)' -> ('Atacama Desert (Yungay)', 'Chile')"""
    m = re.match(r"^(.*?)\s*\((.*)\)$", full)
    if not m:
        return full, ""
    base, inside = m.groups()
    if " - " in inside:
        extra, country = inside.rsplit(" - ", 1)
        return f"{base} ({extra})", country
    return base, inside


def _weight_vector(weights):
    w = dict(DEFAULT_W)
    for k, v in (weights or {}).items():
        key = k if k in w else ALIASES.get(k)
        if key:
            try:
                w[key] = max(0.0, float(v))
            except (TypeError, ValueError):
                pass
    return np.array([w[f] for f in FEATURES])


# ---------------------------------------------------------------- البحث
def find_matches(body, lat, lon, k=5, weights=None, exclude_known=False):
    body = str(body).lower()
    if body == "earth":
        raise ValueError("search from moon or mars; results are Earth sites")
    src = _sites[_sites.world == body]
    if src.empty:
        raise ValueError(f"unknown body: {body}")

    # 1) أقرب موقع مرجعي للنقطة المضغوطة
    qi = src.index[_haversine_km(lat, lon, src.lat.to_numpy(), src.lon.to_numpy()).argmin()]
    zq = _Z[qi]
    q_raw = _sites.loc[qi, FEATURES].astype(float)

    # 2) مسافة موزونة لكل مواقع الأرض
    w = _weight_vector(weights)
    d = np.sqrt((((_Z[_earth_idx] - zq) * w) ** 2).sum(axis=1))
    if exclude_known:
        d = np.where(_sites.loc[_earth_idx, "is_known"].to_numpy(), np.inf, d)

    # 3) أقرب k
    order = [j for j in np.argsort(d) if np.isfinite(d[j])][:k]

    out = []
    for rank, j in enumerate(order, 1):
        i = _earth_idx[j]
        row = _sites.loc[i]
        name, country = _split_name(row["region_name"])
        gap = np.abs(_Z[i] - zq)
        dims = {f: float(1 / (1 + gap[n])) for n, f in enumerate(FEATURES)}
        worst = np.argsort(-gap * w)[:2]
        diffs = [f"{FEATURES[n]}: {q_raw.iloc[n]:.0f} {UNITS[FEATURES[n]]} on {body.title()} "
                 f"vs {float(row[FEATURES[n]]):.0f} {UNITS[FEATURES[n]]} here".replace("  ", " ")
                 for n in worst]
        out.append({
            "rank": rank, "name": name, "country": country,
            "lat": float(row["lat"]), "lon": float(row["lon"]),
            "similarity": float(1 / (1 + d[j])),
            "confidence": None,
            "dimension_scores": dims,
            "risks": BODY_RISKS[body],
            "differences": diffs,
            "is_known": bool(row["is_known"]),
            "note": str(row["similarity_reason"]),
            "matched_from": _sites.loc[qi, "region_name"],
        })
    return out