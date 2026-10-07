"""
PS5 Step 3 - Build the county x year metro panel: OEWS wages + ACS + crosswalk labels.

Usage (from the PS5 folder):
    ../.venv/bin/python ps5_step3_merge.py

Steps:
  1. Start from the provided ../county_oews_crosswalk.csv (one row per county x year; FIPS and
     oews_area read as text so leading zeros survive; oews_area is 7 characters).
  2. Keep counties in an OEWS metropolitan area: oews_area begins with "00". The crosswalk is
     year-specific, so the rule is applied year by year.
  3. Drop Puerto Rico (state FIPS 72), as in the course PS4 answer key, so the county set
     matches PS4 and later problem sets (NDCP has PR prices only for 2021). Also drop two
     retired FIPS codes the crosswalk still lists next to their replacements (12025 -> 12086
     Miami-Dade; 51515 Bedford city -> 51019 Bedford County, VA).
  4. Merge OEWS SOC 39-9011 wages (oews_childcare_workers_2015_2022.csv; area codes already
     zero-padded to 7 characters) on [year, oews_area]. Many counties share one area wage.
  5. Merge ACS county data (acs5_county_2015_2022.csv) on [fips, year].
  6. Label metros with area_title from the crosswalk.

Known gap: the 2022 ACS reports Connecticut by its 9 new planning regions instead of its 8
old counties, while the crosswalk (and NDCP) still use the old counties. The 7 metro CT
counties therefore have no 2022 ACS values; they are left missing rather than imputed.

Output:
    ps5_county_year_metro.csv   one row per metro county x year, 2015-2022
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
YEARS = range(2015, 2023)

# 1. Crosswalk
xw = pd.read_csv(HERE.parent / "county_oews_crosswalk.csv", dtype=str)
xw["year"] = xw["year"].astype(int)
xw = xw.rename(columns={"county_fips": "fips"})
xw["fips"] = xw["fips"].str.zfill(5)
xw["oews_area"] = xw["oews_area"].str.zfill(7)
assert xw["fips"].str.len().eq(5).all() and xw["oews_area"].str.len().eq(7).all()
assert not xw.duplicated(["fips", "year"]).any()
xw = xw[xw["year"].isin(YEARS)]

# 2-3. Metro sample, without Puerto Rico or retired FIPS codes
metro = xw[xw["oews_area"].str.startswith("00")].copy()
# The crosswalk carries two retired county codes next to their replacements: 12025 (old
# Miami-Dade code; 12086 is also present) and 51515 (Bedford city, VA, merged into Bedford
# County 51019 in 2013). Neither has ACS or NDCP data; keeping them would double-count.
RETIRED = {"12025", "51515"}
assert metro.loc[metro["fips"].isin({"12086", "51019"})].groupby("fips")["year"].nunique().eq(8).all()
metro = metro[~metro["fips"].isin(RETIRED)]
n_pr = metro["fips"].str.startswith("72").groupby(metro["year"]).sum()
metro = metro[~metro["fips"].str.startswith("72")]
print("Metro counties per year (crosswalk, PR dropped):", metro.groupby("year").size().to_dict())
print("Puerto Rico metro municipios dropped per year:", n_pr.to_dict())

# 4. OEWS wages
w = pd.read_csv(HERE / "oews_childcare_workers_2015_2022.csv", dtype={"oews_area": str})
w = w.rename(columns={"area_title": "oews_file_area_title", "tot_emp": "cc_workers_emp",
                      "h_mean": "cc_wage_hourly_mean", "a_mean": "cc_wage_annual_mean",
                      "h_median": "cc_wage_hourly_median", "a_median": "cc_wage_annual_median",
                      "emp_prse": "cc_emp_prse", "mean_prse": "cc_wage_mean_prse"})
wage_cols = ["cc_wage_annual_mean", "cc_wage_hourly_mean", "cc_wage_annual_median",
             "cc_wage_hourly_median", "cc_workers_emp", "cc_emp_prse", "cc_wage_mean_prse"]
panel = metro.merge(w[["year", "oews_area", "oews_file_area_title"] + wage_cols],
                    on=["year", "oews_area"], how="left", validate="many_to_one",
                    indicator="oews_merge")

# 5. ACS
acs = pd.read_csv(HERE / "acs5_county_2015_2022.csv", dtype={"fips": str})
acs_vars = ["per_capita_income", "pop_total", "kids_under6", "kids_under6_allpar_lf",
            "median_gross_rent", "female_college_share", "female_ftyr_share",
            "under6_share", "under6_careneed_share"]
panel = panel.merge(acs[["fips", "year", "county_name"] + acs_vars], on=["fips", "year"],
                    how="left", validate="one_to_one", indicator="acs_merge")

# 6. Order columns; area_title comes from the crosswalk
panel = panel[["fips", "year", "state_abbr", "county_name", "oews_area", "area_title"]
              + wage_cols + acs_vars + ["oews_file_area_title", "oews_merge", "acs_merge"]]
panel = panel.sort_values(["fips", "year"]).reset_index(drop=True)
assert not panel.duplicated(["fips", "year"]).any()
panel.to_csv(HERE / "ps5_county_year_metro.csv", index=False)
print(f"\nWrote ps5_county_year_metro.csv {panel.shape}")

# Sanity checks
pd.set_option("display.width", 200)
miss = panel.assign(wage_missing=panel["cc_wage_annual_mean"].isna(),
                    no_oews_row=panel["oews_merge"].eq("left_only"),
                    acs_missing=panel["acs_merge"].eq("left_only"))
summary = miss.groupby("year").agg(counties=("fips", "size"),
                                   wage_missing=("wage_missing", "sum"),
                                   area_not_in_oews=("no_oews_row", "sum"),
                                   acs_not_found=("acs_missing", "sum"))
summary["wage_missing_pct"] = (100 * summary["wage_missing"] / summary["counties"]).round(2)
print("\nSanity check by year:")
print(summary.to_string())
tot = miss["wage_missing"].mean()
print(f"\nOverall share of metro county-years missing the childcare-worker mean annual wage: "
      f"{tot:.2%}  (assignment expects roughly 1%)")
gone = miss[miss["wage_missing"]].groupby(["oews_area", "area_title"])["year"] \
    .agg(lambda s: ",".join(map(str, sorted(s)))).reset_index()
gone["counties"] = miss[miss["wage_missing"]].groupby(["oews_area", "area_title"]).size().values
print("\nMetro areas with a missing wage (years, county-years affected):")
print(gone.to_string(index=False))
print("\nACS missing values in the metro panel:")
print(panel[acs_vars].isna().sum().to_string())
