# Research note: when is conditional allocation worth its turnover?

*Numbers: [results_transfer_french5_final.md](results_transfer_french5_final.md),
[formulations_transfer_french5_final.md](formulations_transfer_french5_final.md),
[results_transfer_french5_dev.md](results_transfer_french5_dev.md),
[results_archival_hw3_dev.md](results_archival_hw3_dev.md). The French final (2019-01..2026-07)
was not used for any design decision and was evaluated once with the frozen procedure; as
declared, its annual expanding-window refits include earlier final-period months. Its first 49
months (2019-01..2023-01) overlap the previously viewed archival period (different series).*

## Verifying the optimizer before using it

The forest's leaves solve a nonconvex problem: maximum mean excess return subject to the
equal-weight variance, full investment and no shorts. Face enumeration in hull coordinates, with
both Lagrange roots, gives the global optimum for five assets and is checked against a multistart
local solver, a two-asset closed form, and batched-versus-exact parity; enumeration is exact
for five assets but exponential in their number. Three defects of the leaf solver in the
original course notebook and one in this project's own first reimplementation were reproduced
with counterexamples and kept as regression tests (none is attributed to the paper). For the
convex relaxation (variance at most the target v), let a and b be the smallest and largest
variance on the face of the best-mean assets. If a <= v the relaxed optimum is the best mean; if
a > v the constraint binds and the two problems share their optimal value and solutions; the
relaxed value is strictly higher exactly when v > b. The solver's "slack" status (a <= v) is
therefore not the same as a value gap (tied means, or a best asset with variance exactly v).
Tests compare the exact relaxed solver with a conic solver (cvxpy with Clarabel) on random leaves
and check the three cases on generic, tied, singular and boundary leaves, with one counterexample
for slack status without a gap and one for a strict gap. On the 317,332 node problems that six
development forests actually met, both formulations were solved on each stored problem: the
relaxed value was strictly higher in 18.1% of them (median 6.7 bp of monthly expected return),
and slack status without a gap occurred only with tied best means
([paired_value_gap.md](paired_value_gap.md)). On binding problems the relaxed solver returns the
equality solution, so there the condition's agreement with the gap is true by construction; on
the 57,552 slack problems it matched in every case (for the 57,522 with a unique best asset this
follows from feasibility; the 30 with tied best means test the enumeration), and an
interior-point solver on 4,000 sampled problems agreed with the exact relaxed values to within
2e-8. A 750-instance benchmark
([leaf_benchmark.md](leaf_benchmark.md)) records feasibility, objective gaps to multistart SLSQP
and cvxpy, statuses, conditioning and runtimes, which grow exponentially with the number of
assets.

## Archival reproduction

On the supplied five-asset index data (previously viewed) the forest reproduces the paper
closely: gross Sharpe 0.64 (seed 0) and 82.8% turnover against the paper's gross 0.68 and 81.51%.
The archival workbook's redistribution terms are not established; only strategy-level summary
statistics derived from it are reported.

## Out of sample

On Kenneth French's five industry portfolios (research return series) with return-derived
state variables, the forest's point estimates were below equal weight's in development
(1947-2018) and in the final period; neither difference is statistically resolved. The only
variant whose point estimate exceeded equal weight's in the final was the relaxed forest with a
no-trade band (seed 0 net Sharpe 0.835 against 0.828; 0.81 averaged over seeds), a difference
well within noise. In the final the forest earned a lower Sharpe ratio before costs and paid
about seven times equal weight's turnover. Shrinkage toward equal weight, with the weight chosen
only on earlier out-of-sample months, moved most of the way to equal weight (all the way with the
convex leaf); the no-trade band and quarterly updates reduced turnover but not the gap in gross
performance.

## Formulation

At forest level, relaxed minus equality net Sharpe was -0.004 in the final (interval -0.017 to
0.014), with similar concentration (mean largest weight 0.448 against 0.451), although the
relaxed solver took its slack branch in about one leaf solve in seven (slack status, which here
nearly always coincides with a value gap, see above) and the two forests' splits differ. In the
archival sample (viewed before) the relaxed forest was slightly worse (-0.017, interval -0.036
to -0.003), plausibly because slack leaves concentrate in a single low-risk asset. Averaging
leaf portfolios across trees already puts the forest inside the risk budget (ex-ante volatility
0.973 of the target on average over the final months), and the estimated formulation effect is
an order of magnitude smaller than the forest's estimated gap to equal weight (-0.05).

## Caveats

Five assets and monthly data make Sharpe differences smaller than about 0.15 unresolvable; state
variables are return-derived (no macro vintages); industry portfolios are research return series,
and 20 bps per unit turnover is an assumed cost.
State variables differ from the paper's (return-derived rather than macro series), so the
French transfer tests the method, not the paper's specification. The contribution is a verified
optimizer, an exact statement of when the relaxation changes the optimal value, and an
out-of-sample result in which conditional allocation showed no benefit that would pay for its
turnover.
