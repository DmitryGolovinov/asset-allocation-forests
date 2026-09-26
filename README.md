# Asset Allocation Forests: Exact Leaf Optimization and an Out-of-Sample Test

I re-implemented the Asset Allocation Forest of Bettencourt, Petukhina & Tetereva (SSRN 4781685):
a random forest splits market states, and each leaf holds the maximum-return portfolio at the
equal-weight volatility. Most of my work went into the leaf problem, which is nonconvex (the
simplex intersected with the surface of an ellipsoid), and into testing the forest out of sample.

This started as my ML in Finance course project at the New Economic School. The course notebook
already enumerated the faces of the simplex, but I found three defects in it with counterexamples
(now regression tests). This version makes the solver exact, adds an exact solution of the convex
relaxation with a condition for when the two differ, a solver benchmark, and an out-of-sample test
on Kenneth French's five industry portfolios.

## Results

- **Exact leaf solver.** `solve_leaf_exact` enumerates all 2^N - 1 faces of the simplex and solves
  each face's stationarity conditions in closed form, keeping both Lagrange roots and handling
  degenerate, singular and zero-variance faces. On a benchmark of 750 instances (N up to 10, six
  families of hard cases) the feasibility residual stayed below 1e-12 and a 20-start SLSQP never
  beat it beyond round-off (3e-12); SLSQP found a worse point on about half of the boundary
  instances with N >= 4. The cost is exponential in N (about 42 ms for ten assets in the saved
  benchmark), which limits this approach to small asset sets.
- **When the relaxation matters.** The convex relaxation (variance at most v) gives a strictly
  higher value exactly when every best-mean asset has variance below v; the proof is short
  ([docs/methodology.md](docs/methodology.md)). Across 317,332 node problems met while growing six
  forests, the relaxed value was higher in 18.1% of them, by a median 6.7 bp of monthly expected
  return.
- **Out of sample** (French five industries, seed 0, 2019-01 to 2026-07, 20 bps per unit turnover). The
  forest did not beat equal weight: net Sharpe 0.77 against 0.83, with 178% annual turnover
  against 24% (bootstrap interval for the Sharpe difference -0.22 to 0.08). Shrinking the forest
  toward equal weight cut turnover to 36% and ended within 0.01 of equal weight.
- **Reproduction** of the paper on the original five-asset data (gross returns): forest Sharpe
  0.64 with 82.8% turnover (paper: 0.68 and 81.51), equal weight 0.52 (paper: 0.50).

| Net Sharpe, seed 0, 20 bps per unit turnover | French 2019-01..2026-07 | French 1947-2018 | Five assets 2003-2023 |
|---|---:|---:|---:|
| Equal weight | 0.83 | 0.57 | 0.52 |
| Forest (paper's equality leaf) | 0.77 | 0.55 | 0.62 |
| Forest with shrinkage toward equal weight | 0.82 | 0.55 | |
| Forest, quarterly updates | 0.78 | 0.57 | 0.63 |
| Forest with the convex (inequality) leaf | 0.77 | 0.54 | |

The French evaluation spans 91 months, including 49 that overlap the archival study's calendar
on different return series. The industry portfolios are research series, and turnover costs
are assumed; [data notes](docs/data.md) describe the scope of the comparison.

![Wealth paths net of costs, French five industries, 2019-2026](reports/figures/wealth_transfer_french5_final.png)

## Data

- Kenneth French Data Library: five industry portfolios and the Fama-French factors, monthly,
  1947-2026. Public.
- The five-asset index workbook from the course (not redistributed; `make data-private` explains
  the local import).

## How it works

- **Leaf** (`src/aaf/leaf.py`): exact equality solver, exact relaxed solver and the case analysis.
- **Forest** (`src/aaf/forest.py`): depth 3, minimum leaf 36, 200 bagged trees, split thresholds at
  node deciles, node moments from cumulative sums.
- **Backtest** (`src/aaf/backtest.py`, `src/aaf/study.py`): annual expanding-window refits,
  drifting weights, turnover costs, shrinkage toward equal weight chosen on earlier out-of-sample
  months, joint block bootstrap for Sharpe differences.

## Run

```bash
make test                          # leaf solvers, the relaxation condition, forest, accounting
make demo                          # synthetic two-regime data, no network
make data-public reproduce-public  # French library download and the study
make benchmark value-gap           # solver benchmark and relaxation count
```

Detailed tables: [reports/results_transfer_french5_final.md](reports/results_transfer_french5_final.md),
[reports/leaf_benchmark.md](reports/leaf_benchmark.md),
[reports/paired_value_gap.md](reports/paired_value_gap.md).

## References

- L. O. Bettencourt, A. Petukhina, A. Tetereva. Advancing Markowitz: Asset Allocation Forest.
  SSRN Working Paper 4781685, 2024.
- L. Breiman. Random Forests. *Machine Learning* 45(1), 2001.
- Kenneth R. French Data Library.
