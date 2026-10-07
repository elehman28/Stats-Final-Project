"""
PS5 Step 1 - Download ACS 5-year county estimates (2015-2022) from the Census API.

Usage (from the PS5 folder):
    ../.venv/bin/python ps5_step1_acs.py

API key: the Census API requires a free key (https://api.census.gov/data/key_signup.html).
The script reads it from the CENSUS_API_KEY environment variable, or else from the file
../.census_api_key (one line, project root, so it is NOT inside the PS5 folder you submit).
The key is never printed or written to any output.

Variables (assignment table; codes and labels checked identical in the 2015 and 2022
variables.json):
    per_capita_income        B19301_001E   (nominal dollars of each ACS year)
    pop_total                B01001_001E
    kids_under6              B23008_002E   own children under 6
    kids_under6_allpar_lf    B23008_004E + _010E + _013E   under 6, all resident parents in LF
    median_gross_rent        B25064_001E   monthly, nominal dollars of each ACS year
    female_college_share     (B15002_032E + 033E + 034E + 035E) / B15002_019E   women 25+
    female_ftyr_share        B23022_029E / B23022_026E   women 16-64 full-time year-round
    under6_share             kids_under6 / pop_total
    under6_careneed_share    kids_under6_allpar_lf / pop_total

"year" is the ACS 5-year vintage: year 2022 = survey years 2018-2022.
Census sentinel values (negative codes such as -666666666 for "not available") are set
to missing.

Outputs:
    raw/acs/acs5_YYYY_raw.json          raw API responses
    acs5_county_2015_2022.csv           county x year, fips as 5-character string
"""
import json
import os
import sys
import time
import ssl
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import certifi
import pandas as pd

HERE = Path(__file__).parent
SSL_CTX = ssl.create_default_context(cafile=certifi.where())  # python.org macOS builds lack system certs
RAW = HERE / "raw" / "acs"
RAW.mkdir(parents=True, exist_ok=True)
YEARS = range(2015, 2023)

RAW_VARS = ["B19301_001E", "B01001_001E",
            "B23008_002E", "B23008_004E", "B23008_010E", "B23008_013E",
            "B25064_001E",
            "B15002_019E", "B15002_032E", "B15002_033E", "B15002_034E", "B15002_035E",
            "B23022_026E", "B23022_029E"]


def get_key():
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    keyfile = HERE.parent / ".census_api_key"
    if not key and keyfile.exists():
        key = keyfile.read_text().strip()
    if not key:
        sys.exit("No Census API key. Put it in ../.census_api_key or set CENSUS_API_KEY.")
    return key


def fetch(year, key):
    out = RAW / f"acs5_{year}_raw.json"
    if out.exists():
        return json.loads(out.read_text())
    params = {"get": "NAME," + ",".join(RAW_VARS), "for": "county:*", "in": "state:*", "key": key}
    url = f"https://api.census.gov/data/{year}/acs/acs5?" + urlencode(params, safe=":*,")
    for attempt in range(3):
        try:
            with urlopen(url, timeout=120, context=SSL_CTX) as r:
                data = json.loads(r.read().decode())
            out.write_text(json.dumps(data))
            return data
        except Exception as e:  # report without echoing the URL (it contains the key)
            print(f"  {year}: attempt {attempt + 1} failed ({type(e).__name__})")
            time.sleep(3)
    sys.exit(f"Could not download ACS {year}.")


key = get_key()
frames = []
for year in YEARS:
    data = fetch(year, key)
    d = pd.DataFrame(data[1:], columns=data[0])
    d["year"] = year
    frames.append(d)
    print(f"ACS {year}: {len(d):,} counties")
acs = pd.concat(frames, ignore_index=True)

acs["fips"] = acs["state"].str.zfill(2) + acs["county"].str.zfill(3)
assert acs["fips"].str.len().eq(5).all()
for v in RAW_VARS:
    acs[v] = pd.to_numeric(acs[v], errors="coerce")
    acs.loc[acs[v] < 0, v] = pd.NA  # Census annotation sentinels
    acs[v] = acs[v].astype(float)

acs["per_capita_income"] = acs["B19301_001E"]
acs["pop_total"] = acs["B01001_001E"]
acs["kids_under6"] = acs["B23008_002E"]
acs["kids_under6_allpar_lf"] = acs[["B23008_004E", "B23008_010E", "B23008_013E"]].sum(axis=1, min_count=3)
acs["median_gross_rent"] = acs["B25064_001E"]
acs["female_college_share"] = (acs[["B15002_032E", "B15002_033E", "B15002_034E", "B15002_035E"]]
                               .sum(axis=1, min_count=4) / acs["B15002_019E"])
acs["female_ftyr_share"] = acs["B23022_029E"] / acs["B23022_026E"]
acs["under6_share"] = acs["kids_under6"] / acs["pop_total"]
acs["under6_careneed_share"] = acs["kids_under6_allpar_lf"] / acs["pop_total"]

derived = ["per_capita_income", "pop_total", "kids_under6", "kids_under6_allpar_lf",
           "median_gross_rent", "female_college_share", "female_ftyr_share",
           "under6_share", "under6_careneed_share"]
out = acs[["fips", "year", "NAME"] + derived + RAW_VARS].rename(columns={"NAME": "county_name"})
out = out.sort_values(["fips", "year"])
assert not out.duplicated(["fips", "year"]).any()
out.to_csv(HERE / "acs5_county_2015_2022.csv", index=False)

pd.set_option("display.width", 200)
print(f"\nWrote acs5_county_2015_2022.csv {out.shape}")
print("\nCounties per year:", out.groupby("year").size().to_dict())
print("Puerto Rico rows per year:", out[out["fips"].str.startswith("72")].groupby("year").size().to_dict())
print("\nMissing values by variable (all years):")
print(out[derived].isna().sum().to_string())
print("\n2022 summary:")
print(out[out["year"] == 2022][derived].describe().T[["count", "mean", "std", "min", "max"]].round(3).to_string())
for c in ["female_college_share", "female_ftyr_share", "under6_share", "under6_careneed_share"]:
    assert out[c].dropna().between(0, 1).all(), c
