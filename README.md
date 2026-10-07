# MGT-403 Data Project: Where Should We Open Our Next Daycare?

Elise Lehman, Yale SOM. Code and outputs for the MGT-403 data project: Problem Set 4
(childcare prices), Problem Set 5 (cost drivers), and the final project.

## Layout

```
county_oews_crosswalk.csv     course-provided county x year -> OEWS area crosswalk
PS4/                          Problem Set 4: distribution of childcare prices
PS5/                          Problem Set 5: cost drivers (ACS, OEWS wages)
```

Each folder's scripts are numbered and run in order from inside that folder.

### PS4

| Script | What it does | Main outputs |
|---|---|---|
| `ps4_step1_metro_sample.py` | NDCP 2015-2022, zero-padded FIPS, OEWS metro filter (`oews_area` begins `00`) | `ndcp_2015_2022_metro.csv` |
| `ps4_step2_histograms_2022.py` | Q2: 2022 histograms, mean / SD / N, 95% CIs | `ps4_q2_*` |
| `ps4_step3_real_trends.py` | Q3: CPI-U deflation to 2022 dollars, trends (all counties and balanced panel) | `ndcp_2015_2022_metro_real.csv`, `ps4_q3_*` |
| `ps4_step4_ccdf_voucher_test.py` | Q4: one-sample t-tests of the CCDF voucher, 2022 and 2015 | `ps4_q4_voucher_test.csv` |
| `build_ps4_pdf.py` | Assembles the write-up from the outputs and `ps4_my_answers.txt` | `PS4_Lehman.pdf` |

### PS5

| Script | What it does | Main outputs |
|---|---|---|
| `ps5_step1_acs.py` | Q1: ACS 5-year county estimates 2015-2022 via the Census API; derived variables | `acs5_county_2015_2022.csv` |
| `ps5_step2_oews.py` | Q2: SOC 39-9011 childcare-worker wages by OEWS area, 2015-2022 | `oews_childcare_workers_2015_2022.csv` |
| `ps5_step3_merge.py` | Q3: crosswalk + wages + ACS, metro counties only, with sanity checks | `ps5_county_year_metro.csv` |
| `ps5_step4_descriptives_2022.py` | Q4: mean / SD / N of each predictor, 2022 | `ps5_q4_descriptives_2022.*` |

## Reproducing

```bash
python3 -m venv .venv
.venv/bin/pip install -r PS4/requirements.txt -r PS5/requirements.txt
cd PS4 && ../.venv/bin/python ps4_step1_metro_sample.py ../NDCP2022.xlsx ../county_oews_crosswalk.csv
```

Raw inputs not stored in this repo (large or require a key):

- **NDCP2022.xlsx** (county workbook): U.S. Department of Labor, National Database of
  Childcare Prices, https://www.dol.gov/agencies/wb/topics/featured-childcare. Place it in the
  repo root.
- **OEWS area files**: `https://www.bls.gov/oes/special-requests/oesmYYma.zip` for
  YY = 15...22. Place the zips in `PS5/raw/oews/`. BLS blocks scripted downloads without a
  contact User-Agent; download in a browser or set `BLS_USER_AGENT`.
- **Census API key** (free, https://api.census.gov/data/key_signup.html): save it to
  `.census_api_key` in the repo root (git-ignored) or set `CENSUS_API_KEY`. Raw ACS responses
  are cached in `PS5/raw/acs/`.
- **CPI-U** (BLS series CUUR0000SA0, annual averages) is saved in `PS4/cpi_u_annual.csv`.

## Key data handling decisions

- FIPS codes (5 characters) and OEWS area codes (7 characters) are always read as text and
  zero-padded.
- Metro sample: counties whose year-specific `oews_area` begins with `00`.
- Puerto Rico is dropped from PS5 onward (NDCP has PR prices only for 2021), matching the
  course answer key. PS4 kept it; it affects only the all-counties 2021 point in PS4 Q3.
- Two retired FIPS codes in the crosswalk are dropped: 12025 (old Miami-Dade code; 12086 is
  present) and 51515 (Bedford city, VA, merged into 51019 in 2013).
- OEWS 2015-2017: parent-metro wages come from the `aMSA_` file, because the main `MSA_` file
  splits large metros into metropolitan divisions.
- The 2022 ACS reports Connecticut by planning region, not county, so Connecticut's 7 metro
  counties have no 2022 ACS values (left missing).
- About 0.7% of metro county-years have no childcare-worker wage, where BLS published no
  estimate for the area.

AI use: Claude Code (Anthropic) wrote and ran the scripts at my direction; see the note in
`PS4/PS4_Lehman.pdf`.
