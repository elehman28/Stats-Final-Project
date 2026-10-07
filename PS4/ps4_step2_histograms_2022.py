"""
PS4 Step 2 - 2022 center-based median weekly prices by age group (metro sample).

Usage:
    python ps4_step2_histograms_2022.py [ndcp_2015_2022_metro.csv]

Outputs:
    ps4_q2_histograms_2022.png   three histograms (infant / toddler / preschool), shared x-axis
    ps4_q2_summary_2022.csv      mean / SD / N / SE / 95% CI per age group
    ps4_q2_summary_by_flag_2022.csv   same stats split by price flag (sensitivity check)

95% CI for the mean uses the t distribution: mean +/- t(0.975, N-1) * SD / sqrt(N),
with SD the sample standard deviation (ddof=1). Counties with a missing price for
an age group are dropped for that age group only.
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

path = sys.argv[1] if len(sys.argv) > 1 else "ndcp_2015_2022_metro.csv"
df = pd.read_csv(path, dtype={"fips": str, "oews_area": str})
d = df[df["year"] == 2022].copy()
print(f"2022 metro counties: {len(d)} (unique FIPS: {d['fips'].nunique()})")

groups = [("Infant", "mc_infant"), ("Toddler", "mc_toddler"), ("Preschool", "mc_preschool")]


def summarize(x):
    x = x.dropna()
    n = len(x)
    mean, sd = x.mean(), x.std(ddof=1)
    se = sd / np.sqrt(n)
    t = stats.t.ppf(0.975, n - 1)
    return {"n": n, "mean": mean, "sd": sd, "se": se, "t_crit": t,
            "ci_low": mean - t * se, "ci_high": mean + t * se,
            "median": x.median(), "min": x.min(), "max": x.max()}


# 1. Summary table
rows = []
for label, col in groups:
    s = summarize(d[col])
    s["n_missing"] = int(d[col].isna().sum())
    rows.append({"age_group": label, **s})
summary = pd.DataFrame(rows)
summary.round(2).to_csv("ps4_q2_summary_2022.csv", index=False)
pd.set_option("display.width", 200)
print("\nCenter-based median weekly price, 2022, metro counties (nominal $):")
print(summary[["age_group", "n", "n_missing", "mean", "sd", "se",
               "ci_low", "ci_high", "median"]].round(2).to_string(index=False))

# Missing prices by state (who drops out of each age group)
miss = d[d["mc_preschool"].isna()]["STATE_ABBREVIATION"].value_counts()
print("\nCounties missing 2022 preschool price, by state:", miss.to_dict())

# Paired differences on the common set of counties with all three prices
both = d.dropna(subset=[c for _, c in groups])
print(f"\nCounties with all three prices: {len(both)}")
for (la, ca), (lb, cb) in [(groups[0], groups[1]), (groups[1], groups[2]), (groups[0], groups[2])]:
    diff = both[ca] - both[cb]
    s = summarize(diff)
    print(f"  {la} - {lb}: mean diff ${s['mean']:.2f}, 95% CI [{s['ci_low']:.2f}, {s['ci_high']:.2f}], "
          f"share of counties where {la} > {lb}: {(diff > 0).mean():.1%}, "
          f"where equal: {(diff == 0).mean():.1%}")

# 2. Sensitivity: stats by price flag (flag meanings unverified - see NDCP tech report App. C)
flag_rows = []
for label, col in groups:
    for flag, sub in d.groupby(col + "_flag"):
        flag_rows.append({"age_group": label, "flag": int(flag), **summarize(sub[col])})
by_flag = pd.DataFrame(flag_rows)
by_flag.round(2).to_csv("ps4_q2_summary_by_flag_2022.csv", index=False)
print("\nBy price flag (sensitivity; flag meanings unverified):")
print(by_flag[["age_group", "flag", "n", "mean", "sd"]].round(2).to_string(index=False))

# 3. Histograms: one panel per age group, shared x-axis and bins for comparability
COLOR = "#2a78d6"
INK, MUTED = "#1f1f1e", "#6b6a64"
bins = np.arange(75, d[[c for _, c in groups]].max().max() + 25, 20)

fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True, sharey=True)
for ax, (label, col), (_, s) in zip(axes, groups, summary.iterrows()):
    ax.hist(d[col].dropna(), bins=bins, color=COLOR, edgecolor="white", linewidth=1.5)
    ax.axvline(s["mean"], color=INK, linewidth=1.5)
    ax.axvspan(s["ci_low"], s["ci_high"], color=INK, alpha=0.15, linewidth=0)
    ax.set_title(label, loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.text(0.98, 0.92,
            f"Mean \\${s['mean']:.2f}   SD \\${s['sd']:.2f}   N = {s['n']}\n"
            f"95% CI for mean: [\\${s['ci_low']:.2f}, \\${s['ci_high']:.2f}]",
            transform=ax.transAxes, ha="right", va="top", fontsize=9.5, color=INK)
    ax.set_ylabel("Counties", color=MUTED)
    ax.grid(axis="y", color="#e6e5df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#bdbcb4")
    ax.tick_params(colors=MUTED)
axes[-1].set_xlabel("Median weekly price, center-based care (2022, nominal \\$)", color=MUTED)
fig.suptitle("Center-based childcare prices by age group, 2022 metro counties",
             x=0.02, ha="left", fontsize=13, color=INK)
fig.text(0.02, 0.005, "Source: DOL NDCP 2022, counties in OEWS metro areas. "
         "Bins \\$20 wide. Line = mean; shaded band = 95% CI for mean.",
         fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 0.97))
fig.savefig("ps4_q2_histograms_2022.png", dpi=200)
print("\nWrote ps4_q2_histograms_2022.png, ps4_q2_summary_2022.csv, ps4_q2_summary_by_flag_2022.csv")
