"""
PS5 Step 2 - Childcare-worker (SOC 39-9011) wages by OEWS area, 2015-2022.

Usage (from the PS5 folder):
    ../.venv/bin/python ps5_step2_oews.py

Input: the BLS OEWS metropolitan & nonmetropolitan area files, oesmYYma.zip for YY = 15..22,
from https://www.bls.gov/oes/special-requests/oesmYYma.zip, saved in raw/oews/.
BLS blocks automated downloads unless the request's User-Agent includes contact
information. If the environment variable BLS_USER_AGENT is set (e.g. "Name email@x.edu"),
missing zips are downloaded with it; otherwise download them in a browser into raw/oews/.

Each zip holds one file for metropolitan areas (MSA_M20YY_dl.xlsx) and one for
nonmetropolitan areas (BOS_M20YY_dl.xlsx). For 2015-2017 the MSA file reports large metros
only by metropolitan division (e.g., Chicago-Naperville-Arlington Heights, IL); the parent
metro areas the crosswalk uses (e.g., 0016980 Chicago) are in a third file, aMSA_M20YY_dl.xlsx. Column names change case across years
(AREA vs area), so they are lower-cased. AREA is zero-padded to the 7-character code used
in county_oews_crosswalk.csv. BLS marks suppressed or unavailable estimates with "*",
"#" (wage at or above the top-coded level), or "**"; these become missing, and the
original string is kept in a *_raw column so top-coding is visible.

Outputs:
    oews_childcare_workers_2015_2022.csv   one row per OEWS area x year for SOC 39-9011
"""
import os
import re
import sys
import zipfile
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

import certifi
import pandas as pd

HERE = Path(__file__).parent
SSL_CTX = ssl.create_default_context(cafile=certifi.where())  # python.org macOS builds lack system certs
RAW = HERE / "raw" / "oews"
RAW.mkdir(parents=True, exist_ok=True)
YEARS = range(2015, 2023)
SOC = "39-9011"
KEEP = ["tot_emp", "emp_prse", "h_mean", "a_mean", "mean_prse", "h_median", "a_median"]


def ensure_zip(year):
    path = RAW / f"oesm{year % 100:02d}ma.zip"
    if path.exists():
        return path
    ua = os.environ.get("BLS_USER_AGENT", "").strip()
    if not ua:
        sys.exit(f"Missing {path.name}. Download https://www.bls.gov/oes/special-requests/"
                 f"{path.name} into {RAW}, or set BLS_USER_AGENT.")
    req = Request(f"https://www.bls.gov/oes/special-requests/{path.name}",
                  headers={"User-Agent": ua})
    with urlopen(req, timeout=300, context=SSL_CTX) as r:
        path.write_bytes(r.read())
    print(f"Downloaded {path.name}")
    return path


def read_area_file(zf, member):
    with zf.open(member) as fh:
        df = pd.read_excel(fh, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


frames = []
for year in YEARS:
    zpath = ensure_zip(year)
    with zipfile.ZipFile(zpath) as zf:
        # MSA_ = metro areas, BOS_ = nonmetro areas, aMSA_ (2015-2017 only) = parent metros
        # that BLS split into metropolitan divisions in the MSA_ file. The crosswalk uses
        # parent-metro codes, so aMSA_ is needed. Skip Excel lock files ("~$...").
        members = [m for m in zf.namelist()
                   if re.match(r"(a?msa|bos)_m\d{4}_dl\.xlsx?$", Path(m).name, re.I)]
        if not 2 <= len(members) <= 3:
            sys.exit(f"{zpath.name}: expected MSA, BOS (and aMSA) files, found {members}")
        for m in members:
            name = Path(m).name.lower()
            kind = ("nonmetro" if name.startswith("bos") else
                    "metro_parent" if name.startswith("amsa") else "metro")
            df = read_area_file(zf, m)
            occ = df[df["occ_code"].str.strip() == SOC].copy()
            occ["year"] = year
            occ["area_type"] = kind
            occ["source_file"] = Path(m).name
            frames.append(occ)
            print(f"{year} {Path(m).name}: {len(df):,} rows, {len(occ)} areas with {SOC}")

w = pd.concat(frames, ignore_index=True)
w["oews_area"] = w["area"].str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(7)
assert w["oews_area"].str.len().eq(7).all()
out = w[["year", "oews_area", "area_title", "area_type", "occ_code", "occ_title"]].copy()
for c in KEEP:
    raw = w[c].astype(str).str.strip()
    out[c] = pd.to_numeric(raw.str.replace(",", ""), errors="coerce")
    flagged = out[c].isna() & w[c].notna()
    if flagged.any():
        out[c + "_raw"] = raw.where(flagged)
out = out.sort_values(["year", "oews_area"])
assert not out.duplicated(["year", "oews_area"]).any()
out.to_csv(HERE / "oews_childcare_workers_2015_2022.csv", index=False)

pd.set_option("display.width", 200)
print(f"\nWrote oews_childcare_workers_2015_2022.csv {out.shape}")
print("\nAreas per year by type:")
print(out.groupby(["year", "area_type"]).size().unstack().to_string())
print("\nMissing annual mean wage by year:")
print(out.groupby("year")["a_mean"].apply(lambda s: s.isna().sum()).to_string())
if "a_mean_raw" in out:
    print("Suppression codes for a_mean:", out["a_mean_raw"].value_counts().to_dict())
print("\nMean annual wage (nominal), metro areas:")
print(out[out["area_type"].str.startswith("metro")].groupby("year")["a_mean"].describe()[["count", "mean", "std", "min", "max"]].round(0).to_string())

# Coverage against the course crosswalk: every metro area code should be found
xw = pd.read_csv(HERE.parent / "county_oews_crosswalk.csv", dtype=str)
xw["year"] = xw["year"].astype(int)
xa = xw[["year", "oews_area"]].drop_duplicates()
m = xa.merge(out[["year", "oews_area", "a_mean"]], on=["year", "oews_area"], how="left", indicator=True)
print("\nCrosswalk areas matched to OEWS file, by year:")
print(m.groupby("year")["_merge"].value_counts().unstack(fill_value=0).to_string())
unmatched = m[m["_merge"] == "left_only"]
if len(unmatched):
    print("Unmatched crosswalk areas (first 10):", unmatched.head(10)[["year", "oews_area"]].values.tolist())
