"""
PS4 Step 3 - Convert NDCP prices to constant 2022 dollars (CPI-U) and plot trends.

Usage:
    python ps4_step3_real_trends.py [ndcp_2015_2022_metro.csv] [cpi_u_annual.csv]

CPI-U: BLS series CUUR0000SA0, U.S. city average, all items, not seasonally adjusted,
annual averages (1982-84=100). Pulled from the BLS Public Data API v2 on 2026-09-29 and
saved to cpi_u_annual.csv.

Real price (2022 $) = nominal price * CPI_2022 / CPI_year.

Outputs:
    ndcp_2015_2022_metro_real.csv   metro file with real (2022 $) versions of every price column
    ps4_q3_trends_by_year.csv       per year x age group: N, mean, SD, 95% CI, cross-county median,
                                    nominal and real, for all reporting counties and a balanced panel
    ps4_q3_real_price_trends.png    mean real price by year, all counties vs balanced panel

Sample note: the set of counties with prices changes by year (e.g., 2021 drops VA, NC,
CA, PA counties and is the only year with Puerto Rico prices). The balanced panel keeps
counties with non-missing center-based prices for all three age groups in all 8 years,
so its trend is not driven by counties entering or leaving the data.
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ndcp_path = sys.argv[1] if len(sys.argv) > 1 else "ndcp_2015_2022_metro.csv"
cpi_path = sys.argv[2] if len(sys.argv) > 2 else "cpi_u_annual.csv"

df = pd.read_csv(ndcp_path, dtype={"fips": str, "oews_area": str})
cpi = pd.read_csv(cpi_path)
cpi["deflator"] = cpi.loc[cpi["year"] == 2022, "cpi_u"].item() / cpi["cpi_u"]
print(cpi.round(4).to_string(index=False))

# 1. Real (2022 $) versions of all dollar columns
df = df.merge(cpi[["year", "deflator"]], on="year", how="left", validate="many_to_one")
assert df["deflator"].notna().all()
price_cols = ["mc_infant", "mc_toddler", "mc_preschool",
              "p75c_infant", "p75c_toddler", "p75c_preschool"]
for c in price_cols:
    df[c + "_real"] = df[c] * df["deflator"]
df.to_csv("ndcp_2015_2022_metro_real.csv", index=False)
print(f"\nWrote ndcp_2015_2022_metro_real.csv {df.shape}")

groups = [("Infant", "mc_infant"), ("Toddler", "mc_toddler"), ("Preschool", "mc_preschool")]
years = sorted(df["year"].unique())

# 2. Balanced panel: counties with all three center prices in every year
has_all = df.dropna(subset=[c for _, c in groups])
yrs_per_county = has_all.groupby("fips")["year"].nunique()
balanced_fips = yrs_per_county[yrs_per_county == len(years)].index
balanced = df[df["fips"].isin(balanced_fips)]
print(f"Balanced panel: {len(balanced_fips)} counties with all 3 prices in all {len(years)} years")


def summarize(x):
    x = x.dropna()
    n = len(x)
    mean, sd = x.mean(), x.std(ddof=1)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return {"n": n, "mean": mean, "sd": sd, "ci_low": mean - half,
            "ci_high": mean + half, "median": x.median()}


rows = []
for sample_name, data in [("all", df), ("balanced", balanced)]:
    for year, g in data.groupby("year"):
        for label, col in groups:
            for dollars, c in [("nominal", col), ("real2022", col + "_real")]:
                rows.append({"sample": sample_name, "year": year, "age_group": label,
                             "dollars": dollars, **summarize(g[c])})
trend = pd.DataFrame(rows)
trend.round(2).to_csv("ps4_q3_trends_by_year.csv", index=False)

pd.set_option("display.width", 200)
for sample_name in ["all", "balanced"]:
    t = trend[(trend["sample"] == sample_name)]
    print(f"\nMean center-based weekly price by year ({sample_name} counties)")
    wide = t.pivot_table(index="year", columns=["dollars", "age_group"], values="mean")
    wide[("N", "Preschool")] = t[(t["dollars"] == "real2022") & (t["age_group"] == "Preschool")] \
        .set_index("year")["n"]
    print(wide.round(1).to_string())


def pct(a, b):
    return 100 * (b / a - 1)


print("\nPercent change in mean price (real = 2022 $):")
for sample_name in ["all", "balanced"]:
    t = trend[trend["sample"] == sample_name].set_index(["dollars", "age_group", "year"])["mean"]
    for label, _ in groups:
        n15, n22 = t[("nominal", label, 2015)], t[("nominal", label, 2022)]
        r15, r19, r20, r22 = (t[("real2022", label, y)] for y in (2015, 2019, 2020, 2022))
        print(f"  {sample_name:8s} {label:9s} nominal 2015-22: {pct(n15, n22):+5.1f}%   "
              f"real 2015-22: {pct(r15, r22):+5.1f}% (${r22 - r15:+.2f}/wk)   "
              f"real 2015-19: {pct(r15, r19):+5.1f}%   real 2020-22: {pct(r20, r22):+5.1f}%")
print(f"  CPI-U 2015-22: {pct(cpi['cpi_u'].iloc[0], cpi['cpi_u'].iloc[-1]):+.1f}%")

# Within-county real change 2015 -> 2022 on the balanced panel (paired)
b = balanced.pivot_table(index="fips", columns="year",
                         values=[c + "_real" for _, c in groups])
print("\nBalanced panel, within-county real change 2015->2022:")
for label, col in groups:
    diff = b[(col + "_real", 2022)] - b[(col + "_real", 2015)]
    s = summarize(diff)
    print(f"  {label:9s} mean ${s['mean']:+.2f}/wk, 95% CI [{s['ci_low']:+.2f}, {s['ci_high']:+.2f}], "
          f"share of counties with a real increase: {(diff > 0).mean():.1%}")

# 3. Plot: mean real price by year, two panels (all reporting counties | balanced panel)
COLORS = {"Infant": "#2a78d6", "Toddler": "#eb6834", "Preschool": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5df"

fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
panels = [("all", "All reporting metro counties"),
          ("balanced", f"Balanced panel ({len(balanced_fips)} counties, every year)")]
for ax, (sample_name, title) in zip(axes, panels):
    t = trend[(trend["sample"] == sample_name) & (trend["dollars"] == "real2022")]
    for label, _ in groups:
        s = t[t["age_group"] == label].sort_values("year")
        ax.fill_between(s["year"], s["ci_low"], s["ci_high"], color=COLORS[label],
                        alpha=0.15, linewidth=0)
        ax.plot(s["year"], s["mean"], color=COLORS[label], linewidth=2,
                marker="o", markersize=5, markeredgecolor="white", markeredgewidth=1.2,
                label=label)
        last = s.iloc[-1]
        ax.annotate(f"{label} \\${last['mean']:.0f}", (last["year"], last["mean"]),
                    xytext=(8, 0), textcoords="offset points", va="center",
                    fontsize=9.5, color=INK)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK, fontweight="bold")
    ax.set_xticks(years)
    ax.set_xlim(years[0] - 0.3, years[-1] + 1.4)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#bdbcb4")
    ax.tick_params(colors=MUTED)
axes[0].set_ylabel("Mean of county median weekly price (2022 \\$)", color=MUTED)
axes[0].legend(frameon=False, loc="upper left", fontsize=9.5)
fig.suptitle("Center-based childcare prices in constant 2022 dollars, 2015-2022",
             x=0.01, ha="left", fontsize=13, color=INK)
fig.text(0.01, 0.01,
         "Source: DOL NDCP 2022 (metro counties via OEWS crosswalk); BLS CPI-U CUUR0000SA0 "
         "annual averages. Shaded bands = 95% CI for the mean.\n2021 in the left panel "
         "drops VA, NC, CA, PA counties and adds Puerto Rico (its only year with prices).",
         fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.06, 1, 0.95))
fig.savefig("ps4_q3_real_price_trends.png", dpi=200)
print("\nWrote ps4_q3_real_price_trends.png, ps4_q3_trends_by_year.csv")
