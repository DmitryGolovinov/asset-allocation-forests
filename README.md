# Asset Allocation Forests: Exact Leaf Optimization and an Out-of-Sample Test

I re-implemented the Asset Allocation Forest of Bettencourt, Petukhina & Tetereva: a forest
partitions market states and assigns each leaf a maximum-return portfolio at equal-weight
volatility. This started as my ML in Finance course project at the New Economic School.
The course notebook already enumerated simplex faces; I corrected its solver using explicit
counterexamples, added an exact convex-relaxation solver, and derived the elementary condition
for a gap between the two optimal values. I then tested whether the forest's allocation gains
survive turnover costs on a different dataset.

## Results

- **Leaf optimization:** on 750 benchmark instances with up to ten assets, equality feasibility
  residuals stayed below `1e-12`. A 20-start SLSQP never improved the objective beyond round-off
  (`3e-12`). Face enumeration is exponential: about 42 ms for ten assets in the saved benchmark,
  so this approach is limited to small asset sets.
- **Relaxation:** allowing variance below the equal-weight target gives a strictly higher
  optimal value exactly when every best-mean asset has variance below that target. This occurred
  in 18.1% of 317,332 node problems encountered in six development forests, with a median gap of
  6.7 bp in estimated monthly mean return. These are optimization problems, not independent
  investment observations.
- **Out of sample:** on five French industry portfolios, January 2019–July 2026, seed 0,
  net Sharpe was 0.77 versus 0.83 for equal weight, at 178% versus 24% annual turnover.
  At an assumed 20 bps per unit turnover, the Sharpe-difference interval was −0.22 to 0.08:
  no statistically resolved benefit. Shrinkage toward equal weight reduced turnover to 36%
  and gave a net Sharpe of 0.82.

![Wealth paths net of costs, French five industries](reports/figures/wealth_transfer_french5_final.png)

The evaluation contains 91 months; 49 overlap the previously viewed archival study's calendar
on different series. Industry portfolios are research return series, and costs are assumptions.
The experiment does not establish performance for a tradable allocation strategy.

[Allocation results](reports/results_transfer_french5_final.md) ·
[Solver benchmark](reports/leaf_benchmark.md) ·
[Paired relaxation comparison](reports/paired_value_gap.md)

## Methods and code

- [Leaf solvers](src/aaf/leaf.py): enumerate the simplex's faces, retain both stationary roots,
  and handle singular and degenerate cases. The [derivation](docs/methodology.md) explains why
  the equality constraint and its convex relaxation can give different answers.
- [Forest](src/aaf/forest.py): 200 bagged trees, depth three, minimum leaf size 36. I use node
  deciles as split candidates; this is a computational change from the paper.
- [Backtest](src/aaf/backtest.py): lagged features, annual expanding-window refits, drifting
  weights and turnover costs. Shrinkage is selected using earlier out-of-sample months.
- [Numerical tests](tests/test_relaxed_theorem.py) compare with an independent interior-point
  solver; [regression tests](tests/test_review_regressions.py) retain concrete counterexamples.

## Data and setup

The public study uses Kenneth French's five industry portfolios and risk-free returns, with
return-derived features. The library can revise history. The original five-asset course workbook
is not redistributed; it is only needed for the [archival reproduction](reports/results_archival_hw3_dev.md).
Input details and private import instructions are in the [data notes](docs/data.md).

Requires Python `3.11` or `3.12`. From this repository:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make check  # offline tests, lint and saved-result claim checks
make demo   # synthetic two-regime example; writes results/demo/
```

`make data-public reproduce-public` downloads public inputs and reruns the development study.
`make benchmark` and `make value-gap` rerun the numerical experiments.
See the [methodology](docs/methodology.md) for evaluation splits and reproduction details.

## References

Bettencourt, Petukhina & Tetereva, *Advancing Markowitz: Asset Allocation Forest*, SSRN 4781685,
2024; Breiman, *Random Forests*, Machine Learning, 2001.
[Full references](docs/references.md).
