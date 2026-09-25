"""Bounded, deterministic check of the relaxation proposition in docs/methodology.md.

With v the equal-weight variance, M the best-mean assets, F_M their face, a and b the minimum and
maximum variance on F_M (b = max of Sigma_ii over M):
(i) a <= v: the relaxed value is max(mu); (ii) a > v: the relaxed constraint binds and the two
optimal values coincide; (iii) the equality value is max(mu) iff a <= v <= b, so the relaxed value
is strictly higher iff v > b. The solver's "slack" status means a <= v, which is not the same as a
value gap (tied best means or a best asset with Sigma_ii = v give slack without a gap).

In its binding branch the relaxed solver returns the equality solution, so comparing the two
solvers there would be circular. The checks below therefore take a and the relaxed optimum from
an interior-point solver (Clarabel via cvxpy), independent of the face enumeration and of the
KKT routine in aaf.leaf."""

import cvxpy as cp
import numpy as np

from aaf.leaf import (
    _face_min_variance,
    ew_variance,
    solve_leaf_exact,
    solve_leaf_relaxed,
    solve_leaf_relaxed_exact,
)

CVX_TOL = 1e-7  # interior-point accuracy margin (observed agreement about 4e-9 on these cases)


def _clarabel_min_variance(S):
    w = cp.Variable(S.shape[0], nonneg=True)
    S = 0.5 * (S + S.T)
    cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(S))), [cp.sum(w) == 1]).solve(
        solver=cp.CLARABEL
    )
    wv = np.maximum(np.asarray(w.value).ravel(), 0.0)
    return wv / wv.sum()


def _face_range(mu, Sigma):
    """a, b and max(mu) for the best-mean face; a from Clarabel (a single asset: Sigma_ii)."""
    top = mu.max()
    M = np.flatnonzero(mu >= top - 1e-14 * max(1.0, abs(top)))
    S = Sigma[np.ix_(M, M)]
    a = float(S[0, 0]) if M.size == 1 else float((w := _clarabel_min_variance(S)) @ S @ w)
    return a, float(np.diag(S).max()), float(top)


def _cases():
    rng = np.random.default_rng(20260924)
    out = []
    for _ in range(60):  # generic leaves
        A = rng.normal(size=(5, 5))
        S = A @ A.T / 5 + np.diag(rng.uniform(0.01, 2, 5))
        out.append(("random", rng.normal(0.01, 0.02, 5), S))
    for _ in range(20):  # two or three tied best means
        A = rng.normal(size=(5, 5))
        S = A @ A.T / 5 + np.diag(rng.uniform(0.01, 2, 5))
        mu = rng.normal(0.0, 0.02, 5)
        mu[rng.choice(5, rng.integers(2, 4), replace=False)] = mu.max() + 0.01
        out.append(("ties", mu, S))
    for _ in range(20):  # tied best means, all with variance far below v
        A = rng.normal(size=(5, 5)) * 0.05
        S = np.diag(rng.uniform(0.5, 2, 5)) + A @ A.T
        idx = rng.choice(5, 2, replace=False)
        S[np.ix_(idx, idx)] = np.diag([0.01, 0.02])
        mu = rng.normal(0, 0.02, 5)
        mu[idx] = mu.max() + 0.01
        out.append(("ties_low", mu, S))
    for _ in range(10):  # singular covariance: asset 4 duplicates asset 0
        A = rng.normal(size=(4, 4))
        S4 = A @ A.T / 4 + np.diag(rng.uniform(0.01, 1, 4))
        S = np.zeros((5, 5))
        S[:4, :4] = S4
        S[4, :4] = S[:4, 4] = S4[0]
        S[4, 4] = S4[0, 0]
        out.append(("singular", rng.normal(0.01, 0.02, 5), S))
    for _ in range(10):  # a zero-variance asset
        A = rng.normal(size=(5, 5))
        S = A @ A.T / 5 + np.diag(rng.uniform(0.01, 1, 5))
        S[3, :] = S[:, 3] = 0
        out.append(("zero_var", rng.normal(0.01, 0.02, 5), S))
    n_boundary = 0
    while n_boundary < 10:  # unique best asset with Sigma_ii = v exactly: x = c + x / 25
        A = rng.normal(size=(5, 5))
        S = A @ A.T / 5 + np.diag(rng.uniform(0.3, 1.5, 5))
        mu = rng.normal(0, 0.02, 5)
        i = int(np.argmax(mu))
        S[i, i] = (S.sum() - S[i, i]) / 24.0
        if np.linalg.eigvalsh(S)[0] > 1e-8:
            out.append(("boundary", mu, S))
            n_boundary += 1
    return out


def test_relaxation_proposition_on_bounded_cases():
    slack_without_gap, counts = {}, {"i": 0, "ii": 0}
    for kind, mu, S in _cases():
        v = ew_variance(S)
        a, b, top = _face_range(mu, S)
        eq = solve_leaf_exact(mu, S)
        rx = solve_leaf_relaxed_exact(mu, S)
        ref = solve_leaf_relaxed(mu, S)  # independent interior-point solve of the relaxation
        tol = 1e-9 * max(1.0, abs(top))
        ctol = CVX_TOL * max(1.0, abs(top))
        assert rx.objective >= eq.objective - tol, kind
        assert abs(rx.objective - ref.objective) <= ctol, kind  # exact relaxed = interior point
        assert a == float(S[np.argmax(mu), np.argmax(mu)]) or abs(a - v) > 1e-6 * v, kind
        if a <= v * (1 + 1e-12):  # (i): the relaxed value is the best mean
            counts["i"] += 1
            assert rx.status == "slack" and abs(rx.objective - top) <= tol, kind
            assert abs(ref.objective - top) <= ctol, kind
        else:  # (ii): the independent relaxed optimum binds and equals the equality value
            counts["ii"] += 1
            assert rx.status.startswith("binding"), kind
            assert abs(ref.objective - eq.objective) <= ctol, kind
            assert abs(float(ref.w @ S @ ref.w) - v) <= 1e-5 * v, kind
        gap = rx.objective - eq.objective > 1e-9
        assert gap == (v > b * (1 + 1e-10)), kind  # (iii)
        assert (ref.objective - eq.objective > 10 * ctol) <= gap, kind  # no gap missed
        if rx.status == "slack" and not gap:
            slack_without_gap[kind] = slack_without_gap.get(kind, 0) + 1
    # both branches are exercised, and the slack status is not a value gap: every boundary case
    # and some tie cases show slack without a gap
    assert counts["i"] > 20 and counts["ii"] > 20
    assert slack_without_gap.get("boundary") == 10
    assert slack_without_gap.get("ties", 0) > 0


def _hard_faces():
    """Faces on which a first-order method converges slowly or not at all."""
    rng = np.random.default_rng(12345)
    out = []
    for _ in range(40):  # rank 3 plus a tiny ridge (condition numbers up to about 1e11)
        B = rng.normal(size=(5, 3))
        out.append(B @ B.T * 1e-3 + np.eye(5) * 10 ** rng.uniform(-14, -6))
    for _ in range(20):  # correlations about 0.999: one common factor plus tiny idiosyncratic risk
        beta = rng.uniform(0.5, 1.5, 4)
        S = 0.04 * np.outer(beta, beta) + np.diag(rng.uniform(1e-5, 4e-5, 4))
        out.append(S)
    for _ in range(20):  # a duplicated asset and a zero-variance asset
        R = rng.normal(size=(3, 5)) * 0.02
        R[:, 4] = R[:, 0]
        R[:, 2] = 0.0
        out.append(np.cov(R.T, bias=True))
    return out


def test_face_min_variance_is_exact_on_hard_faces():
    """The support enumeration attains the interior-point minimum (never worse beyond round-off)
    on near-singular, highly correlated and degenerate faces. This is a one-sided check against a
    solver with its own tolerance; the zero-minimum case below is exact."""
    for S in _hard_faces():
        w = _face_min_variance(S)
        assert abs(w.sum() - 1) < 1e-12 and w.min() >= 0
        wr = _clarabel_min_variance(S)
        scale = float(np.abs(S).max())
        assert w @ S @ w <= wr @ S @ wr + 1e-12 * scale
    # the duplicated and zero-variance case has minimum variance zero (hold the constant asset)
    R = np.array([[0.01, 0.02, 0.0], [-0.02, 0.01, 0.0], [0.03, -0.01, 0.0]])
    S = np.cov(R.T, bias=True)
    w = _face_min_variance(S)
    assert w @ S @ w == 0.0 and w[2] == 1.0


def test_near_tie_is_outside_the_numerical_resolution_of_the_gap_condition():
    """Best and second-best means 5e-13 apart are not a tie at the solver's 1e-14 tolerance, so
    the condition predicts a gap; the realized gap is at most the mean difference and falls
    below the 1e-12 gap threshold. Such problems are reported as unresolved, not classified
    (scripts/paired_value_gap.py uses a 1e-9 resolution band)."""
    mu = np.array([0.02, 0.02 - 5e-13, 0.01, 0.0])
    S = np.diag([0.05, 0.40, 0.20, 0.20])
    v = ew_variance(S)
    eq, rx = solve_leaf_exact(mu, S), solve_leaf_relaxed_exact(mu, S)
    assert v > S[0, 0] * (1 + 1e-10)  # the gap condition holds (unique best asset, b < v)
    gap = rx.objective - eq.objective
    assert 0 <= gap <= (mu[0] - mu[1]) + 1e-16 < 1e-12


def test_counterexample_slack_status_without_a_value_gap():
    """Tied best means whose variances straddle v (a <= v <= b): the relaxed solver takes its
    slack branch and returns a different portfolio, but the optimal values are equal."""
    mu = np.array([0.02, 0.02, 0.01, 0.0])
    S = np.diag([0.05, 0.40, 0.20, 0.20])
    eq, rx = solve_leaf_exact(mu, S), solve_leaf_relaxed_exact(mu, S)
    assert rx.status == "slack"
    assert abs(rx.objective - eq.objective) < 1e-12 and abs(eq.objective - 0.02) < 1e-12
    assert np.abs(rx.w - eq.w).max() > 0.1  # different returned portfolios, same value
    assert abs(eq.w @ S @ eq.w - ew_variance(S)) < 1e-12 < ew_variance(S) - rx.w @ S @ rx.w


def test_counterexample_strict_value_gap_with_a_low_variance_best_asset():
    """A unique best asset with variance below v: the relaxation holds it alone (value 0.03)
    while the equality problem must mix to reach variance v (value about 0.021)."""
    mu = np.array([0.03, 0.01, 0.01])
    S = np.diag([0.01, 0.10, 0.10])
    eq, rx = solve_leaf_exact(mu, S), solve_leaf_relaxed_exact(mu, S)
    assert rx.status == "slack" and np.allclose(rx.w, [1, 0, 0])
    assert rx.objective - eq.objective > 0.009
