# Data card

## Archival: supplied five-asset workbook (`HW3_dataset.xlsx`, local import only)

- 474 monthly rows, 1983-08-31..2023-01-31; returns in decimals; RF in decimals per month
  (0.0076 in 1983-08, matching the Fama-French RF convention). One missing value
  (`Inflation change`, first row; not used).
- Assets: Equity, Bonds, Credits, HY (high yield), Comm (commodities). Per the paper: Bloomberg
  indices for HY, credit and commodities (S&P GSCI), Fama-French market for equity, bond returns
  implied by 10-year zero yields. These are index return series, not executable instruments.
- State variables (14, as in the notebook and paper): earnings and dividend yields, equity
  volatility, TED spread, financial-conditions subindices, credit spread, inflation, IP YoY,
  10-year yield, term spread, CAPE. Lagged one month; their publication dates and vintages are
  NOT modeled, so the archival study does not establish real-time availability.
- The whole out-of-sample period (2003-08..2023-01) was viewed in the original exercise: this is
  an archival reproduction, not an untouched test. Redistribution rights are not established;
  the file is never committed (`make data-private` explains the local import). Outputs that
  reproduce its content closely (the asset-statistics table, wealth and weight paths) are not
  published; the public reports keep aggregate statistics only.

## Transfer: Kenneth French Data Library

- `5_Industry_Portfolios_CSV.zip` (value-weighted monthly section) and
  `F-F_Research_Data_Factors_CSV.zip` (RF), retrieved 2026-09-24 01:03 UTC (server Last-Modified
  2026-09-04); SHA-256 digests in `data/french_manifest.json`. Percent units converted to
  decimals; -99.99/-999 sentinels become missing (none present in the value-weighted monthly
  table). 1926-07..2026-07.
- Features are return-derived and known at the end of month t-1: per-industry 12-month and
  1-month returns and 12-month volatility; market 12-month return, 3-month volatility, and
  cross-industry dispersion (18 features).
- Industry portfolios are research return series, not executable quotes. The library revises
  history occasionally; the snapshot hash fixes the version used.
- Development: 1947-07..2018-12 (858 months). Reserved final sample: 2019-01..2026-07; its
  first 49 months (2019-01..2023-01) overlap the previously viewed archival out-of-sample period
  (2003-08..2023-01, different series), so the final is not calendar-fresh.
