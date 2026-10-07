"""
PS4 Step 1 - Restrict NDCP to the metro analysis sample (2015-2022).

Usage:
    python ps4_step1_metro_sample.py ../NDCP2022.xlsx [../county_oews_crosswalk.csv]

Without the crosswalk: writes the 2015-2022 prepared file (padded FIPS, no metro filter).
With the crosswalk:    also writes the metro-only file.
"""
import sys
import pandas as pd

ndcp_path = sys.argv[1]
xwalk_path = sys.argv[2] if len(sys.argv) > 2 else None

# 1. Read NDCP. FIPS as string, then zero-pad to 5 characters (state(2)+county(3)).
df = pd.read_excel(ndcp_path, dtype={"COUNTY_FIPS_CODE": str})
df["fips"] = df["COUNTY_FIPS_CODE"].astype(str).str.strip().str.zfill(5)
assert df["fips"].str.len().eq(5).all()
df = df.rename(columns={"STUDYYEAR": "year"})

# 2. Years 2015-2022 (per assignment)
df = df[df["year"].between(2015, 2022)].copy()

# 3. Keep identifiers + center-based MEDIAN prices (infant/toddler/preschool) + flags,
#    plus center-based 75th percentile in case it's needed later.
keep = ["fips", "year", "STATE_NAME", "STATE_ABBREVIATION", "COUNTY_NAME",
        "MCINFANT", "MCInfant_flag", "MCTODDLER", "MCToddler_flag",
        "MCPRESCHOOL", "MCPreschool_flag",
        "_75CINFANT", "_75CTODDLER", "_75CPRESCHOOL"]
slim = df[keep].rename(columns={
    "MCINFANT": "mc_infant", "MCInfant_flag": "mc_infant_flag",
    "MCTODDLER": "mc_toddler", "MCToddler_flag": "mc_toddler_flag",
    "MCPRESCHOOL": "mc_preschool", "MCPreschool_flag": "mc_preschool_flag",
    "_75CINFANT": "p75c_infant", "_75CTODDLER": "p75c_toddler",
    "_75CPRESCHOOL": "p75c_preschool"})
slim.to_csv("ndcp_2015_2022_prepared.csv", index=False)
print("Prepared file:", slim.shape, "-> ndcp_2015_2022_prepared.csv")

# 4. Metro filter via the OEWS crosswalk (year-specific!)
if xwalk_path:
    xw = pd.read_csv(xwalk_path, dtype=str)
    print("Crosswalk columns:", list(xw.columns))
    # Column names may differ slightly; locate them.
    fips_col = next(c for c in xw.columns if "fips" in c.lower())
    area_col = next(c for c in xw.columns if c.lower() in ("oews_area", "oews area"))
    xw["fips"] = xw[fips_col].str.zfill(5)
    xw[area_col] = xw[area_col].str.zfill(7)
    xw["year"] = xw["year"].astype(int)

    m = slim.merge(xw[["fips", "year", area_col] +
                      [c for c in xw.columns if "title" in c.lower()]],
                   on=["fips", "year"], how="left", indicator=True)
    print(m["_merge"].value_counts())
    metro = m[m[area_col].str.startswith("00", na=False)].drop(columns="_merge")
    metro.to_csv("ndcp_2015_2022_metro.csv", index=False)
    print("Metro sample:", metro.shape, "-> ndcp_2015_2022_metro.csv")
    print(metro.groupby("year")["fips"].nunique())
