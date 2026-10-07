"""
PS5 Step 4 - Descriptive table (mean / SD / N) of each predictor, 2022 metro counties.

Usage (from the PS5 folder):
    ../.venv/bin/python ps5_step4_descriptives_2022.py

Unit of observation: metro county (ps5_county_year_metro.csv, year == 2022; Puerto Rico and
retired FIPS codes already excluded). N counts counties with a non-missing value, so it varies
by variable: the childcare wage is missing where BLS published no estimate for the county's
OEWS area, and the ACS variables are missing for Connecticut's 7 metro counties in 2022
(the 2022 ACS uses planning regions instead of counties).

The childcare wage is measured at the OEWS area level and copied to every county in the
area, so its county-level N overstates the number of independent wage observations. The
area-level statistics are reported in a second row for comparison.

Dollar values are nominal 2022 dollars (2022 is the base year, so they are also real
2022 dollars). Shares are proportions (0-1).

Outputs:
    ps5_q4_descriptives_2022.csv
    ps5_q4_descriptives_2022.md    formatted table for the write-up
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
panel = pd.read_csv(HERE / "ps5_county_year_metro.csv", dtype={"fips": str, "oews_area": str})
d = panel[panel["year"] == 2022]

VARS = [  # (column, label, unit)
    ("cc_wage_annual_mean", "Childcare-worker mean annual wage (SOC 39-9011)", "$"),
    ("per_capita_income", "Per-capita income", "$"),
    ("median_gross_rent", "Median gross rent (monthly)", "$"),
    ("pop_total", "Total population", "count"),
    ("kids_under6", "Own children under 6", "count"),
    ("kids_under6_allpar_lf", "Children under 6, all resident parents in labor force", "count"),
    ("under6_share", "Share of population under 6", "share"),
    ("under6_careneed_share", "Share of population under 6 needing care", "share"),
    ("female_college_share", "Share of women 25+ with bachelor's or higher", "share"),
    ("female_ftyr_share", "Share of women 16-64 working full-time, year-round", "share"),
]

rows = []
for col, label, unit in VARS:
    x = d[col].dropna()
    rows.append({"variable": col, "label": label, "unit": unit, "level": "county",
                 "n": len(x), "mean": x.mean(), "sd": x.std(ddof=1),
                 "min": x.min(), "max": x.max()})
    if col == "cc_wage_annual_mean":
        a = d.drop_duplicates("oews_area")[col].dropna()
        rows.append({"variable": col, "label": label + " - one obs. per metro area",
                     "unit": unit, "level": "metro area", "n": len(a), "mean": a.mean(),
                     "sd": a.std(ddof=1), "min": a.min(), "max": a.max()})
tab = pd.DataFrame(rows)
tab.to_csv(HERE / "ps5_q4_descriptives_2022.csv", index=False)


def fmt(v, unit):
    if unit == "$":
        return f"${v:,.0f}"
    if unit == "share":
        return f"{v:.3f}"
    return f"{v:,.0f}"


lines = ["| Variable | N | Mean | SD | Min | Max |", "|---|---:|---:|---:|---:|---:|"]
for _, r in tab.iterrows():
    lines.append(f"| {r['label']} | {r['n']:,} | {fmt(r['mean'], r['unit'])} | "
                 f"{fmt(r['sd'], r['unit'])} | {fmt(r['min'], r['unit'])} | "
                 f"{fmt(r['max'], r['unit'])} |")
note = (f"\nMetro counties in 2022: {len(d):,} (Puerto Rico excluded). Dollar values in 2022 "
        "dollars; shares are proportions. Wage is an OEWS-area value assigned to each county.\n")
(HERE / "ps5_q4_descriptives_2022.md").write_text(
    "**Table: Predictors, 2022 metro counties**\n\n" + "\n".join(lines) + "\n" + note)

pd.set_option("display.width", 220)
print(f"2022 metro counties: {len(d):,}\n")
print("\n".join(lines))
print(note)
