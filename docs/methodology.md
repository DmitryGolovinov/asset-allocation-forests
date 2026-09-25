# Methodology

## Leaf problem (paper eq. 2 with lambda = 0; excess returns)

maximize mu'w subject to w' Sigma w = v, 1'w = 1, w >= 0, with v = e'Sigma e / N^2 (the EW
variance of the same leaf). The feasible set is the intersection of an ellipsoid surface with the
simplex: nonconvex. With sigma(w) fixed, maximizing the Sharpe ratio equals maximizing mu'w.

On the affine hull of a face S (positive weights on S only), with c1 = 1'S^{-1}mu,
c2 = 1'S^{-1}1, c3 = mu'S^{-1}mu and D = c3 - c1^2/c2 >= 0, the Lagrange conditions give

    w(a) = S^{-1}1 / c2 + (1/(2a)) S^{-1}(mu - (c1/c2) 1),   var = 1/c2 + D / (4a^2)

so feasibility requires v >= 1/c2 and 2a = +/- sqrt(D / (v - 1/c2)). The global optimum is the
best FEASIBLE critical point over all 2^N - 1 faces. Both signs must be kept: on a two-asset face
the equality set is exactly the two roots, and the "minimizing" root can be the only feasible one.
Degenerate faces (D = 0, e.g. equal means) have a constant objective and are optimal iff they
contain a feasible point; one is constructed on the segment from the face's minimum-variance
portfolio to its highest-variance vertex (intermediate value theorem). That minimum-variance
portfolio (also the relaxed solver's choice among tied best means) is computed exactly by
enumerating supports: on each support the stationarity system 2 S_T w_T = nu 1, 1'w_T = 1 is
solved by least squares, every nonnegative solution is a feasible portfolio, and the lowest
variance among them is the optimum, because some optimal solution is a vertex of the optimal set
and its support has a nonsingular system. This replaced a projected-gradient routine capped at
5,000 steps that a review showed to be inaccurate on near-singular faces (variance up to 35 times
the minimum); in the recorded forests the routine is reached only on faces of two or three
assets with exactly tied means (the library's returns have two decimals), where the old and new
weights agree to 1.3e-12 (parity reruns). Solves use Cholesky factorizations, never explicit
inverses. A batched implementation (all faces of a size at once)
is used inside the forest, with exact-path fallback for degenerate/singular leaves (counted).

**Counterexamples found and kept as tests.** Defects (1)-(3) were in the leaf solver of the
original course notebook (`solve_leaf_lambda0_fast`, the starting point of this repository);
defect (4) was in this project's own first reimplementation. The paper states the optimization
problem; none of the defects is attributed to it. (1) The notebook's rule kept only the root with
a > 0 and, when that root was infeasible, fell back to equal weights; multistart search found
higher feasible objectives. (2) Round-off in D let infeasible singleton faces pass the a > 0
check, returning 100% in one asset. (3) With exactly equal means the notebook's formula divided
by a numerically meaningless D and returned a point violating the volatility constraint by ~14%.
(4) The first reimplementation skipped every face whose covariance submatrix was singular
(the notebook instead inverted Sigma_S plus a 1e-6 ridge), although the variance restricted to
the face's affine hull can be positive definite (e.g. a zero-variance asset), and then returned
the equal-weight fallback. Faces are now solved in hull coordinates and skipped only when the
hull-restricted matrix is singular, which is exact (`tests/test_review_regressions.py`).

**Cross-checks (written in this project, hence not independent of it).** Two-asset closed form;
batched vs exact parity (40 random problems); multistart SLSQP reference (never beats
enumeration beyond round-off; local optima observed); singular covariance (duplicated asset); the
minimum-variance boundary; infeasible targets; and the separately labeled convex relaxation
w'Sigma w <= v, which is a different problem (it can put everything in a low-variance best
asset). For the unconditional problem on each refit's full training window (the SR strategy),
the cvxpy relaxation's variance is within 3e-6 of the target at every refit of every run
(minimum ratio 0.9999976), so the constraint binds and both formulations coincide for that
problem; inside the forest the leaves have other moments and the relaxed solver takes its slack
branch in 3.5% (archival), 20.2% (French development) and 14.4% (French final) of leaf solves
(slack status, not a value gap; see below). Enumeration visits 2^N - 1 faces: exact for N = 5,
exponential in N. A reproducible benchmark on 750 instances (N = 2-6, 8 and 10, six families including
near-singular, duplicate, zero-variance, tied-mean and boundary cases) reports feasibility
residuals, objective gaps to multistart SLSQP and cvxpy, statuses, condition numbers and runtimes:
`scripts/leaf_benchmark.py`, [reports/leaf_benchmark.md](../reports/leaf_benchmark.md).

## The convex formulation at forest level (Generation 1b)

Relaxed leaf: maximize mu'w subject to w'Sigma w <= v, 1'w = 1, w >= 0. Exact solution:
`leaf.solve_leaf_relaxed_exact`.

**Proposition.** Let Delta be the simplex, v = e'Sigma e / N^2 > 0 (the equal-weight point is
feasible for both problems), M the set of assets with the largest mean mu*, F_M = conv{e_i : i in
M} their face, a = min over F_M of w'Sigma w and b = max over F_M of w'Sigma w = max over i in M of
Sigma_ii (a convex function is maximized over a polytope at a vertex). Let V_eq and V_rx be the
optimal values of the equality and relaxed problems.

- (i) If a <= v, then V_rx = mu*, and the relaxed optimizers are exactly the points of F_M with
  variance <= v; the solver returns the minimum-variance one.
- (ii) If a > v, every relaxed optimum has variance exactly v; V_rx = V_eq < mu*, and the two
  problems have the same optimizers.
- (iii) V_eq = mu* if and only if a <= v <= b. Hence V_rx > V_eq if and only if v > b: every
  best-mean asset has variance strictly below v (for a unique best asset i: Sigma_ii < v).

*Proof.* On Delta, mu'w <= mu* with equality exactly on F_M, which gives (i). For (ii): if a
relaxed optimum w* had variance < v, a neighborhood of w* in Delta would be feasible, so w* would
be a local and hence (linear objective, convex set) global maximizer of mu'w on Delta, i.e. a
point of F_M with variance < v, contradicting a > v. So every relaxed optimum is feasible for the
equality problem, whose feasible set is contained in the relaxed one; the values are equal, every
equality optimizer attains V_rx, and every relaxed optimizer attains V_eq. For (iii): the points
of Delta with value mu* are the points of F_M; F_M is connected and the variance is continuous, so
F_M contains a point with variance exactly v iff a <= v <= b. If v > b no equality-feasible point
reaches mu* and, the feasible set being compact, V_eq < mu* = V_rx. If a > v, V_rx = V_eq by (ii).

**What the proposition does and does not say.** It is about optimal values and optimizer sets of
one leaf problem. (a) The solver's "slack" status means a <= v; it is not a value gap: with tied
best means and a <= v <= b, or a unique best asset with Sigma_ii = v, the values coincide although
the returned relaxed portfolio can have variance below v and differ from the returned equality
portfolio. (b) With ties the optimizer sets are not singletons, so equal values do not imply equal
returned portfolios. (c) Equal leaf values do not make the two forests similar: the relaxed
forest's split criterion uses the relaxed leaf Sharpe ratios, so its trees differ. Tests: cvxpy
(Clarabel) comparison on 60 random leaves and a tied-mean face (`tests/test_leaf.py`); a bounded
deterministic check of (i)-(iii) and of (a) on 130 generic, tied, low-variance-tie, singular,
zero-variance and boundary leaves (`tests/test_relaxed_theorem.py`). In that check a and the
relaxed optimum come from Clarabel, not from the solver under test: in the binding case (ii) the
relaxed solver returns the equality solution by construction, so comparing the two solvers there
would be circular. The same file tests the face minimum-variance routine against Clarabel on
near-singular (condition numbers up to about 1e11), highly correlated, duplicated and
zero-variance faces, and shows that a near tie (best means 5e-13 apart) lies outside the
numerical resolution of the gap condition.

**Two counterexamples** (`tests/test_relaxed_theorem.py`). Slack status without a value gap:
mu = (0.02, 0.02, 0.01, 0), Sigma = diag(0.05, 0.40, 0.20, 0.20) gives v = 0.053125, a =
0.044 < v < b = 0.40; both optimal values equal mu* = 0.02, while the returned portfolios
differ (equality (0.75, 0.25, 0, 0), relaxed (0.889, 0.111, 0, 0) at variance 0.044). A strict
gap: mu = (0.03, 0.01, 0.01), Sigma = diag(0.01, 0.10, 0.10) gives v = 0.02333 > b = 0.01, so
the relaxed value is 0.03 and the equality value 0.020985.

**Measured on stored node problems.** Every (mean, covariance) that six development forests
passed to the leaf solver during growth (317,332 problems) was solved under both formulations.
On a binding problem the relaxed solver returns the equality solution, so the condition's
agreement with the realized gap there is true by construction; on the 57,552 slack problems,
where the two values come from different computations, it matched in every case, with no problem
in the 1e-9 resolution band. For the 57,522 of them with a unique best asset (variance below v)
the match follows from feasibility alone, since every feasible equality point has a lower mean;
the 30 with tied best means (2 with a gap, 28 without) are the ones that test the enumeration. A Clarabel solve of the relaxation on 3,000 binding and 1,000 slack
problems drawn at random never exceeded an equality optimum on a binding problem (largest
difference -2e-11) and agreed with the exact relaxed values to within 2e-8; its solutions lay
slightly inside the risk constraint (median relative variance shortfall 6e-8, largest 0.4% where
the two best means differ by 1e-7, so the objective is nearly flat there). Slack status occurred
without a gap only with tied best means ([reports/paired_value_gap.md](../reports/paired_value_gap.md);
`scripts/paired_value_gap.py`; development data only, 10-15 minutes on one core).

In the forest the relaxed leaf reports its own Sharpe ratio when slack (a single low-variance
best-mean asset, or the minimum-variance mix of tied assets), which is the split criterion.
Everything else (hyperparameters, seeds, costs, extensions, bootstrap) is unchanged. Declared in
`configs/g1b_formulation.yaml` before any relaxed-forest result; the French final sample is
the confirmation sample for both formulations.

## Forest (paper Section 3.2)

Node value SR* from the leaf problem on the node's rows; split Z_j < c admissible if both children
have >= 36 rows and both children's SR* >= the parent's; choose the split maximizing
SR*_L / n_L + SR*_R / n_R (eq. 3, as printed); depth <= 3; mtry features per split (4 of 14; 6 of
18 in the transfer); 200 trees on bootstrap resamples; the forest weight is the mean of tree
weights. Deviation: thresholds are node deciles (9 per feature) rather than all observed values.
Node moments come from cumulative sums. Refit every 12 months on an expanding window; weights for
month t use Z_{t-1}.

**Mixing breaks the equality.** Variance is convex, so averaging feasible leaf portfolios (the
forest) or shrinking toward EW produces variance below v, not equal to it. The forest's ex-ante
volatility relative to the EW target is reported (mean 0.95 on the archival data).

## Extension: shrinkage and trading controls

- Shrinkage w(alpha) = alpha w_AAF + (1 - alpha) w_EW, alpha in {0, .25, .5, .75, 1} chosen at each
  refit by net Sharpe (20 bps) on all PRIOR out-of-sample months (default 0.5 before 36 months).
- No-trade band: trade to the AAF target only if ||target - drifted||_1 > b, b in {0, .05, .1, .2,
  .3}, chosen the same way (path-dependent simulation).
- Quarterly updates of the AAF target (fixed control); a fixed alpha = 0.5 mixture for reference.
- The paper's own turnover penalty (lambda > 0) is not presented as a contribution and is not run.

## Accounting and evaluation

Turnover entering month t: sum |w_t - w_{t-1}^+| with drifted weights; the first month buys from
cash. Net return r - c * TO (paper convention). Metrics as in the paper's Table 5 (SR on excess
returns). Break-even cost: cost at which net wealth equals EW's net wealth at the same cost (fixed
schedules). Uncertainty: circular block bootstrap (12-month blocks) resampling the same months for
all strategies (joint across assets), distinct from tree bagging; seed dispersion over seeds
{0, 1, 2}; sequential 60-month blocks.


## Final evaluation (reproduction)

The reserved final samples were evaluated exactly once, on 2026-09-24, with the frozen code
and protocols recorded in each result manifest (`results/*final*/manifest*.json`). The commands
(from the repository root, after `make data-public` (and `make data-private` for the archival study) and the development runs) were:

```bash
python scripts/run_study.py --dataset transfer_french5 --mode final --i-understand-this-is-the-final-evaluation
python scripts/run_study.py --dataset transfer_french5 --mode final --leaf relaxed --i-understand-this-is-the-final-evaluation
python scripts/run_study.py --dataset transfer_french5 --mode final --compare-formulations --i-understand-this-is-the-final-evaluation
python scripts/make_report.py transfer_french5_final transfer_french5_final_relaxed
```

Re-running them reproduces the published final artifacts from the recorded data snapshot (a new
download can differ: Kenneth French library revisions); it is not a new untouched test. Comments in configuration
files written before the release call the final evaluation "Stage 3" (the project's internal
stage names); they are left unchanged because the runs record those files' hashes.
Historical manifests keep the source tree that produced them; `docs/release_lineage.json`
records why each still stands under the current code.
