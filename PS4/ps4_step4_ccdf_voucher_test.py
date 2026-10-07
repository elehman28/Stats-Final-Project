"""
PS4 Step 4 - Test whether the CCDF center-based preschool voucher equals the price of care
at the median-priced center in the average metro county.

Usage:
    python ps4_step4_ccdf_voucher_test.py [ndcp_2015_2022_metro.csv]

Voucher (monthly, nominal): 2022 = $706, 2015 = $473. Weekly equivalent = monthly / 4.33.
Prices and vouchers are both nominal dollars of the same year, so no CPI adjustment is needed.

H0: mu = voucher_weekly   vs   H1: mu != voucher_weekly   (two-sided, alpha = 0.05)
where mu is the population mean of county median weekly center-based preschool prices
across metro counties.

Test statistic: t = (xbar - mu0) / (s / sqrt(n)),  ~ t(n-1) under H0
p-value:        p = 2 * [1 - F_{t, n-1}(|t|)]

Outputs:
    ps4_q4_voucher_test.csv   manual and scipy results for 2022 and 2015 (+ metro-area robustness)
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

path = sys.argv[1] if len(sys.argv) > 1 else "ndcp_2015_2022_metro.csv"
df = pd.read_csv(path, dtype={"fips": str, "oews_area": str})

WEEKS_PER_MONTH = 4.33
ALPHA = 0.05
VOUCHER_MONTHLY = {2022: 706, 2015: 473}

rows = []
for year, monthly in VOUCHER_MONTHLY.items():
    x = df.loc[df["year"] == year, "mc_preschool"].dropna()
    mu0 = monthly / WEEKS_PER_MONTH

    # (b) Manual calculation, element by element
    n = len(x)
    xbar = x.sum() / n
    s = np.sqrt(((x - xbar) ** 2).sum() / (n - 1))
    se = s / np.sqrt(n)
    t_manual = (xbar - mu0) / se
    dof = n - 1
    t_crit = stats.t.ppf(1 - ALPHA / 2, dof)
    p_manual = 2 * stats.t.sf(abs(t_manual), dof)  # sf = 1 - cdf, computed without underflow
    ci = (xbar - t_crit * se, xbar + t_crit * se)

    # (c) Statistical package
    res = stats.ttest_1samp(x, popmean=mu0, alternative="two-sided")
    assert np.isclose(res.statistic, t_manual) and np.isclose(res.pvalue, p_manual)

    print(f"\n===== {year}: voucher ${monthly}/month =====")
    print(f"  mu0 = {monthly} / {WEEKS_PER_MONTH} = ${mu0:.4f}/week")
    print(f"  n            = {n}")
    print(f"  xbar         = sum(x)/n = {x.sum():.2f} / {n} = ${xbar:.4f}")
    print(f"  s            = sqrt(sum((x-xbar)^2)/(n-1)) = ${s:.4f}")
    print(f"  SE = s/sqrt(n) = {s:.4f} / {np.sqrt(n):.4f} = {se:.4f}")
    print(f"  xbar - mu0   = {xbar - mu0:.4f}")
    print(f"  t (manual)   = {xbar - mu0:.4f} / {se:.4f} = {t_manual:.4f}")
    print(f"  t (scipy)    = {res.statistic:.4f}")
    print(f"  df = {dof}, critical |t| at 5% = {t_crit:.4f}")
    print(f"  p (manual)   = 2*(1 - F_t,{dof}(|t|)) = {p_manual:.3e}")
    print(f"  p (scipy)    = {res.pvalue:.3e}")
    print(f"  95% CI for mean price: [${ci[0]:.2f}, ${ci[1]:.2f}]  (mu0 inside? {ci[0] <= mu0 <= ci[1]})")
    print(f"  In monthly terms: mean price ${xbar * WEEKS_PER_MONTH:.2f}/month vs voucher ${monthly}; "
          f"gap ${(xbar - mu0) * WEEKS_PER_MONTH:.2f}/month ({100 * (xbar / mu0 - 1):.1f}% above voucher)")
    print(f"  Share of counties with median price above voucher: {(x > mu0).mean():.1%}")
    print(f"  Decision: {'REJECT' if res.pvalue < ALPHA else 'FAIL TO REJECT'} H0 at 5%")
    rows.append({"unit": "county", "year": year, "voucher_monthly": monthly, "mu0_weekly": mu0,
                 "n": n, "mean": xbar, "sd": s, "se": se, "t_manual": t_manual,
                 "t_scipy": res.statistic, "df": dof, "t_crit": t_crit,
                 "p_value": res.pvalue, "ci_low": ci[0], "ci_high": ci[1],
                 "share_above_voucher": (x > mu0).mean(), "reject_5pct": res.pvalue < ALPHA})

# Robustness: the claim is about the "average metro area". Collapse counties to OEWS metro
# areas (simple mean of county prices within area) and repeat the test on area means.
print("\n===== Robustness: unit = OEWS metro area (mean of its counties) =====")
for year, monthly in VOUCHER_MONTHLY.items():
    mu0 = monthly / WEEKS_PER_MONTH
    a = (df[df["year"] == year].dropna(subset=["mc_preschool"])
         .groupby("oews_area")["mc_preschool"].mean())
    res = stats.ttest_1samp(a, popmean=mu0)
    print(f"  {year}: {len(a)} metro areas, mean ${a.mean():.2f}, SD ${a.std(ddof=1):.2f}, "
          f"t = {res.statistic:.3f}, p = {res.pvalue:.3e}")
    rows.append({"unit": "metro_area", "year": year, "voucher_monthly": monthly, "mu0_weekly": mu0,
                 "n": len(a), "mean": a.mean(), "sd": a.std(ddof=1),
                 "se": a.std(ddof=1) / np.sqrt(len(a)), "t_scipy": res.statistic,
                 "df": len(a) - 1, "p_value": res.pvalue,
                 "share_above_voucher": (a > mu0).mean(), "reject_5pct": res.pvalue < ALPHA})

pd.DataFrame(rows).to_csv("ps4_q4_voucher_test.csv", index=False)
print("\nWrote ps4_q4_voucher_test.csv")
