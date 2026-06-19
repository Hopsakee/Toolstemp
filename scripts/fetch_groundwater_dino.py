#!/usr/bin/env python3
"""
Fetch Dutch groundwater-level data (DINOloket / BRO) and build the data file
for groundwater-nl.html.

It selects ~100 well-spread monitoring tubes that each have a (near) complete
25-year record, computes the trend in the *median summer* (apr–sep) and
*median winter* (oct–mar) groundwater level, and writes the result into the
map as an embedded `GROUNDWATER_DATA` object.

Data source
-----------
Basisregistratie Ondergrond (BRO) public REST services, the modern home of the
DINOloket groundwater data:
    https://publiek.broservices.nl/gm/gld/v1   (Grondwaterstandonderzoek / GLD)
    https://publiek.broservices.nl/gm/gmw/v1   (monitoring wells / GMW)
Accessed via the `hydropandas` library, which handles the WaterML parsing.

NETWORK NOTE
------------
The BRO hosts must be reachable. In a sandboxed environment add
`publiek.broservices.nl` to the network egress allowlist first.

Usage
-----
    pip install -r scripts/requirements.txt
    python scripts/fetch_groundwater_dino.py            # full run
    python scripts/fetch_groundwater_dino.py --quick    # smaller/faster test

Output
------
    groundwater_data.json        (raw selected stations)
    groundwater-nl.html          (GROUNDWATER_DATA placeholder replaced in place)
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dino")
logging.getLogger("hydropandas").setLevel(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
HTML_FILE = ROOT / "groundwater-nl.html"
JSON_FILE = ROOT / "groundwater_data.json"

# ----- analysis period: the past 25 hydrological years -----
END_YEAR = 2025
START_YEAR = END_YEAR - 24                      # 2001..2025 inclusive = 25 years
TMIN = f"{START_YEAR - 1}-10-01"                # capture winter 2000/2001
TMAX = f"{END_YEAR}-12-31"

SUMMER_MONTHS = {4, 5, 6, 7, 8, 9}              # zomerhalfjaar apr–sep
# winter = oct–mar, labelled by the year of its jan–mar part

MIN_YEARS = 22                                  # of 25, per season (allow small gaps)
MIN_SPAN_START = START_YEAR + 1                 # must have data this early ...
MIN_SPAN_END = END_YEAR - 1                     # ... and this late (truly spans 25 yr)

# Netherlands extent in RD New (EPSG:28992): [xmin, xmax, ymin, ymax]
NL_EXTENT = (10000, 280000, 305000, 620000)

QUALITY_BAD = {"afgekeurd"}                     # drop rejected measurements


# --------------------------------------------------------------------------- #
def season_medians(df: pd.DataFrame):
    """Return (years, summer_median, winter_median) per analysis year."""
    s = df["values"].dropna()
    if "qualifier" in df.columns:
        good = ~df["qualifier"].isin(QUALITY_BAD)
        s = s[good.reindex(s.index, fill_value=True)]
    if s.empty:
        return None
    idx = s.index
    month = idx.month
    year = idx.year

    summer_year = np.where(np.isin(month, list(SUMMER_MONTHS)), year, np.nan)
    # winter: oct,nov,dec -> next year; jan,feb,mar -> same year
    winter_year = np.full(len(s), np.nan)
    winter_year[np.isin(month, [10, 11, 12])] = year[np.isin(month, [10, 11, 12])] + 1
    winter_year[np.isin(month, [1, 2, 3])] = year[np.isin(month, [1, 2, 3])]

    vals = s.values
    summer, winter = {}, {}
    for y in range(START_YEAR, END_YEAR + 1):
        sv = vals[summer_year == y]
        wv = vals[winter_year == y]
        if sv.size:
            summer[y] = float(np.median(sv))
        if wv.size:
            winter[y] = float(np.median(wv))
    return summer, winter


def linreg(years, vals):
    """Linear trend; returns slope (cm/yr), r2, p-value (two-sided t-test)."""
    x = np.asarray(years, float)
    y = np.asarray(vals, float)
    n = len(x)
    if n < 3:
        return None
    x0 = x - x.mean()
    sxx = (x0 ** 2).sum()
    if sxx == 0:
        return None
    slope = (x0 * (y - y.mean())).sum() / sxx          # m per year
    intercept = y.mean() - slope * x.mean()
    resid = y - (intercept + slope * x)
    ss_res = (resid ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # p-value for slope
    if n > 2 and ss_res > 0:
        se = np.sqrt(ss_res / (n - 2) / sxx)
        t = slope / se if se > 0 else 0.0
        try:
            from scipy import stats
            p = 2 * stats.t.sf(abs(t), n - 2)
        except Exception:
            # normal approximation fallback
            p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    else:
        p = 1.0
    return dict(slope_cm_yr=round(slope * 100, 3), r2=round(float(r2), 3),
                p=round(float(p), 4))


def evaluate(df: pd.DataFrame):
    """Build the per-station season summary, or None if coverage insufficient."""
    res = season_medians(df)
    if res is None:
        return None
    summer, winter = res
    sy, wy = sorted(summer), sorted(winter)
    if len(sy) < MIN_YEARS or len(wy) < MIN_YEARS:
        return None
    if not (sy[0] <= MIN_SPAN_START and sy[-1] >= MIN_SPAN_END):
        return None
    if not (wy[0] <= MIN_SPAN_START and wy[-1] >= MIN_SPAN_END):
        return None

    def pack(d):
        years = list(range(START_YEAR, END_YEAR + 1))
        med = [round(d[y], 3) if y in d else None for y in years]
        present = [(y, d[y]) for y in years if y in d]
        reg = linreg([y for y, _ in present], [v for _, v in present])
        if reg is None:
            return None
        return dict(median=med, n=len(present), **reg)

    s_pack, w_pack = pack(summer), pack(winter)
    if s_pack is None or w_pack is None:
        return None
    completeness = s_pack["n"] + w_pack["n"]
    return s_pack, w_pack, completeness


# --------------------------------------------------------------------------- #
def fetch_box(extent, GroundwaterObs):
    """Download all groundwater tubes in an RD extent as an ObsCollection."""
    import hydropandas as hpd
    try:
        oc = hpd.read_bro(extent=list(extent), tmin=TMIN, tmax=TMAX,
                          only_metadata=False, keep_all_obs=False,
                          ignore_max_obs=True)
        return oc
    except Exception as e:  # noqa: BLE001
        log.warning("box %s failed: %s", extent, e)
        return None


def to_wgs84():
    from pyproj import Transformer
    return Transformer.from_crs(28992, 4326, always_xy=True)


def run(cell_km: float, box_km: float, target: int, max_per_cell: int):
    from hydropandas import GroundwaterObs

    xmin, xmax, ymin, ymax = NL_EXTENT
    step = cell_km * 1000
    half = box_km * 1000 / 2
    transformer = to_wgs84()

    # grid node centres
    xs = np.arange(xmin + step / 2, xmax, step)
    ys = np.arange(ymin + step / 2, ymax, step)
    nodes = [(x, y) for y in ys for x in xs]
    log.info("Scanning %d grid nodes (%.0f km spacing), period %d-%d",
             len(nodes), cell_km, START_YEAR, END_YEAR)

    selected = []
    for i, (cx, cy) in enumerate(nodes, 1):
        box = (cx - half, cx + half, cy - half, cy + half)
        oc = fetch_box(box, GroundwaterObs)
        if oc is None or len(oc) == 0:
            continue

        best = None
        count = 0
        for name, row in oc.iterrows():
            if count >= max_per_cell:
                break
            obs = row.get("obs")
            if obs is None or getattr(obs, "empty", True):
                continue
            if "values" not in obs.columns:
                continue
            count += 1
            ev = evaluate(obs)
            if ev is None:
                continue
            s_pack, w_pack, completeness = ev
            if best is None or completeness > best[0]:
                x = row.get("x", getattr(obs, "x", None))
                y = row.get("y", getattr(obs, "y", None))
                if x is None or y is None:
                    continue
                lon, lat = transformer.transform(float(x), float(y))
                gl = row.get("ground_level", getattr(obs, "ground_level", None))
                try:
                    gl = None if gl is None or pd.isna(gl) else round(float(gl), 2)
                except Exception:  # noqa: BLE001
                    gl = None
                loc = row.get("location", getattr(obs, "location", str(name)))
                tube = row.get("tube_nr", getattr(obs, "tube_nr", None))
                best = (completeness, dict(
                    id=str(loc), tube=int(tube) if tube is not None else None,
                    name=f"{loc}" + (f"-{int(tube)}" if tube is not None else ""),
                    lat=round(float(lat), 5), lon=round(float(lon), 5),
                    ground_level=gl, summer=s_pack, winter=w_pack))

        if best is not None:
            selected.append(best[1])
            log.info("[%d/%d] node ok -> %s (total %d)",
                     i, len(nodes), best[1]["id"], len(selected))
        if len(selected) >= target:
            log.info("Reached target of %d stations.", target)
            break

    return selected


# --------------------------------------------------------------------------- #
def write_outputs(stations):
    payload = dict(
        demo=False,
        generated=date.today().isoformat(),
        period=dict(start=START_YEAR, end=END_YEAR),
        years=list(range(START_YEAR, END_YEAR + 1)),
        summer_months=sorted(SUMMER_MONTHS),
        source="BRO / DINOloket grondwaterstandonderzoek (GLD)",
        stations=stations,
    )
    JSON_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info("Wrote %s (%d stations)", JSON_FILE.name, len(stations))

    if HTML_FILE.exists():
        html = HTML_FILE.read_text()
        inline = "const GROUNDWATER_DATA = " + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ) + "; /* __DATA_PLACEHOLDER__ */"
        new = re.sub(r"const GROUNDWATER_DATA = .*?/\* __DATA_PLACEHOLDER__ \*/",
                     lambda _: inline, html, count=1, flags=re.S)
        if new == html:
            log.warning("Placeholder not found in %s; HTML not updated.", HTML_FILE.name)
        else:
            HTML_FILE.write_text(new)
            log.info("Injected data into %s", HTML_FILE.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cell-km", type=float, default=22,
                    help="grid spacing between selected stations (km)")
    ap.add_argument("--box-km", type=float, default=8,
                    help="search box size per grid node (km)")
    ap.add_argument("--target", type=int, default=100,
                    help="number of stations to select")
    ap.add_argument("--max-per-cell", type=int, default=40,
                    help="max tubes inspected per grid node")
    ap.add_argument("--quick", action="store_true",
                    help="fast smoke test: coarse grid, few stations")
    args = ap.parse_args()

    if args.quick:
        args.cell_km, args.box_km, args.target, args.max_per_cell = 60, 6, 12, 15

    try:
        import hydropandas  # noqa: F401
    except ImportError:
        log.error("hydropandas not installed. Run: pip install -r scripts/requirements.txt")
        sys.exit(1)

    stations = run(args.cell_km, args.box_km, args.target, args.max_per_cell)
    if not stations:
        log.error("No qualifying stations found. Is the BRO host reachable "
                  "(publiek.broservices.nl)? Try a larger --box-km.")
        sys.exit(2)
    write_outputs(stations)
    log.info("Done. Open groundwater-nl.html to view the map.")


if __name__ == "__main__":
    main()
