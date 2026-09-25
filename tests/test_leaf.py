import numpy as np
import pytest

from aaf.leaf import (
    FastLeafSolver,
    ew_variance,
    legacy_solver,
    solve_leaf_exact,
    solve_leaf_reference,
    solve_leaf_relaxed,
)


def _random_problem(seed, n=5, T=60):
    rng = np.random.default_rng(seed)
    A = rng.normal(size=(n, n))
    vols = rng.uniform(0.01, 0.06, n)
    C = np.corrcoef(rng.normal(size=(T, n)) @ A, rowvar=False)
    Sigma = C * np.outer(vols, vols)
    mu = rng.normal(0.004, 0.004, n)
    return mu, Sigma


def test_two_asset_face_keeps_the_second_root():
    # Regression for a counterexample found by the multistart cross-check: the optimum can be
    # the "minimizing" root of a two-asset face, which the notebook's a > 0 rule discarded,
    # sending the solver to an equal-weight fallback.
    mu, Sigma = _random_problem(100)
    ex = solve_leaf_exact(mu, Sigma)
    ref = solve_leaf_reference(mu, Sigma, starts=20, seed=0)
    assert ex.status == "ok" and ex.objective >= ref.objective - 1e-10
    old = legacy_solver_from_moments(mu, Sigma)
    v = ew_variance(Sigma)
    old_infeasible = abs(old @ Sigma @ old - v) / v > 1e-6
    # The old rule either misses the optimum or (via round-off in D on singleton faces,
    # a second defect) returns a portfolio that violates the volatility equality.
    assert old_infeasible or mu @ old < ex.objective - 1e-4


def legacy_solver_from_moments(mu, Sigma):
    """Notebook rule (a > 0 root only) applied to given moments, for the regression test."""
    import itertools

    n = mu.size
    v = ew_variance(Sigma)
    best = None
    for k in range(1, n + 1):
        for S in itertools.combinations(range(n), k):
            S = list(S)
            A = np.linalg.inv(Sigma[np.ix_(S, S)])
            e = np.ones(k)
            c1, c2, c3 = e @ A @ mu[S], e @ A @ e, mu[S] @ A @ mu[S]
            if v <= 1 / c2:
                continue
            a = 0.5 * np.sqrt(max(c3 - c1**2 / c2, 0) / (v - 1 / c2))
            if a <= 0:
                continue
            wS = A @ (mu[S] - (c1 - 2 * a) / c2 * e) / (2 * a)
            if wS.min() < -1e-8:
                continue
            w = np.zeros(n)
            w[S] = wS
            if best is None or mu @ w > mu @ best:
                best = w
    return np.full(n, 1 / n) if best is None else best


def test_two_asset_closed_form():
    # w = (a, 1-a): var(a) = a^2 s11 + 2a(1-a) s12 + (1-a)^2 s22 = v has two roots; the one
    # with larger mu'w in [0, 1] is the optimum.
    mu = np.array([0.01, 0.004])
    Sigma = np.array([[0.0025, 0.0003], [0.0003, 0.0009]])
    v = ew_variance(Sigma)
    s11, s12, s22 = Sigma[0, 0], Sigma[0, 1], Sigma[1, 1]
    A = s11 - 2 * s12 + s22
    B = 2 * (s12 - s22)
    C = s22 - v
    roots = [(-B + sgn * np.sqrt(B * B - 4 * A * C)) / (2 * A) for sgn in (1, -1)]
    roots = [a for a in roots if 0 <= a <= 1]
    a_best = max(roots, key=lambda a: mu @ np.array([a, 1 - a]))
    r = solve_leaf_exact(mu, Sigma)
    assert r.w == pytest.approx([a_best, 1 - a_best], abs=1e-12)
    assert r.feasibility_residual < 1e-12


@pytest.mark.parametrize("seed", range(40))
def test_fast_matches_exact_and_is_feasible(seed):
    mu, Sigma = _random_problem(seed)
    ex = solve_leaf_exact(mu, Sigma)
    w, sr = FastLeafSolver(5).solve(mu, Sigma)
    assert np.allclose(w, ex.w, atol=1e-9)
    assert sr == pytest.approx(ex.sr, rel=1e-9)
    assert ex.feasibility_residual < 1e-9
    assert ex.w.min() >= 0 and abs(ex.w.sum() - 1) < 1e-12


def test_exact_dominates_multistart_reference():
    # Multistart SLSQP is a local cross-check without a global certificate: it may stop at a
    # worse local optimum (seen for seed 109), but it must never beat the enumeration.
    agree = 0
    for seed in range(100, 130):
        mu, Sigma = _random_problem(seed)
        ex = solve_leaf_exact(mu, Sigma)
        ref = solve_leaf_reference(mu, Sigma, starts=20, seed=seed)
        assert ex.objective >= ref.objective - 1e-10
        agree += ex.objective - ref.objective < 1e-8
    assert agree >= 24


def test_equal_means_face_is_not_skipped():
    # Counterexample for the original solver: with equal means every face is degenerate
    # (D = 0) and the notebook skipped them all, falling back to EW. Here any feasible point
    # is optimal; the exact solver must return a feasible one.
    _, Sigma = _random_problem(7)
    mu = np.full(5, 0.003)
    r = solve_leaf_exact(mu, Sigma)
    assert r.feasibility_residual < 1e-8
    assert r.objective == pytest.approx(0.003)
    R = np.random.default_rng(0).multivariate_normal(np.full(5, 0.003), Sigma, 400)
    # Construct data whose sample means are exactly equal: demean and add a constant.
    R = R - R.mean(axis=0) + 0.003
    w_legacy = legacy_solver(R, np.zeros(len(R)), ridge=0.0)
    S_hat = np.cov(R, rowvar=False)
    v = ew_variance(S_hat)
    # D is ~1e-20 instead of 0, so the notebook formula divides by a numerically meaningless
    # quantity and returns a point that violates the volatility constraint by ~14%.
    assert abs(w_legacy @ S_hat @ w_legacy - v) / v > 0.05
    ours = solve_leaf_exact(R.mean(axis=0), S_hat)
    assert ours.feasibility_residual < 1e-8


def test_singular_covariance_with_duplicate_asset():
    mu, Sigma = _random_problem(3, n=4)
    mu = np.r_[mu, mu[0]]
    S = np.zeros((5, 5))
    S[:4, :4] = Sigma
    S[4, :4] = S[:4, 4] = Sigma[0]
    S[4, 4] = Sigma[0, 0]  # asset 4 duplicates asset 0: Sigma is singular
    r = solve_leaf_exact(mu, S)
    ref = solve_leaf_reference(mu, S, starts=30)
    assert r.feasibility_residual < 1e-8
    assert r.objective >= ref.objective - 1e-10
    w, _ = FastLeafSolver(5).solve(mu, S)
    assert mu @ w == pytest.approx(r.objective, abs=1e-10)


def test_minimum_variance_boundary_gives_unique_point():
    mu, Sigma = _random_problem(11)
    import cvxpy as cp

    w = cp.Variable(5, nonneg=True)
    cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(Sigma))), [cp.sum(w) == 1]).solve()
    wmin = np.maximum(w.value, 0) / np.maximum(w.value, 0).sum()
    vmin = float(wmin @ Sigma @ wmin)
    r = solve_leaf_exact(mu, Sigma, v=vmin * (1 + 1e-12))
    assert np.allclose(r.w, wmin, atol=1e-4)


def test_infeasible_target_reports_fallback():
    mu, Sigma = _random_problem(12)
    r = solve_leaf_exact(mu, Sigma, v=1e-12)
    assert r.status == "fallback_ew"


def test_relaxation_is_a_different_problem():
    # The best asset has LOWER variance than the EW portfolio: the relaxed problem puts
    # everything in it, while the equality problem must take extra risk.
    mu = np.array([0.008, 0.002, 0.001])
    Sigma = np.diag([0.0004, 0.0036, 0.0049])
    v = ew_variance(Sigma)
    assert Sigma[0, 0] < v
    rel = solve_leaf_relaxed(mu, Sigma)
    ex = solve_leaf_exact(mu, Sigma)
    assert rel.w[0] == pytest.approx(1.0, abs=1e-6)
    assert ex.feasibility_residual < 1e-10 and ex.w[0] < 0.999
    assert rel.objective >= ex.objective - 1e-12


def test_mixing_feasible_portfolios_leaves_the_equality_surface():
    # var is convex, so alpha*w1 + (1-alpha)*w2 has variance <= v: shrinkage and forest
    # averaging do NOT preserve the equality constraint (they land inside the relaxed set).
    mu, Sigma = _random_problem(5)
    v = ew_variance(Sigma)
    w1 = solve_leaf_exact(mu, Sigma).w
    w2 = solve_leaf_exact(-mu, Sigma).w
    for a in (0.25, 0.5, 0.75):
        w = a * w1 + (1 - a) * w2
        assert w @ Sigma @ w <= v + 1e-15
    w = 0.5 * w1 + 0.5 * w2
    assert w @ Sigma @ w < v * (1 - 1e-6)


def test_relaxed_exact_matches_cvxpy_and_equality_when_binding():
    """Exact relaxed solver versus the cvxpy relaxation on random leaves; when the constraint
    binds the solution coincides with the equality optimum."""
    from aaf.leaf import FastLeafSolver, solve_leaf_relaxed_exact

    rng = np.random.default_rng(7)
    fast = FastLeafSolver(5, "relaxed")
    n_slack = n_bind = 0
    for _ in range(60):
        A = rng.normal(size=(5, 5))
        Sigma = A @ A.T / 5 + np.diag(rng.uniform(0.01, 2.0, 5))
        mu = rng.normal(0.01, 0.02, 5)
        ex = solve_leaf_relaxed_exact(mu, Sigma)
        cv = solve_leaf_relaxed(mu, Sigma)
        assert ex.objective >= cv.objective - 1e-6
        assert abs(ex.objective - cv.objective) < 1e-5
        assert ex.w @ Sigma @ ex.w <= ew_variance(Sigma) * (1 + 1e-9)
        w_f, sr_f = fast.solve(mu, Sigma)
        np.testing.assert_allclose(mu @ w_f, ex.objective, rtol=1e-9, atol=1e-12)
        if ex.status == "slack":
            n_slack += 1
            assert sr_f == pytest.approx(ex.sr)
        else:
            n_bind += 1
            eq = solve_leaf_exact(mu, Sigma)
            assert ex.objective == pytest.approx(eq.objective, rel=1e-12)
    assert n_slack > 0 and n_bind > 0 and fast.slack == n_slack


def test_relaxed_tied_best_assets_take_min_variance_mix():
    from aaf.leaf import solve_leaf_relaxed_exact

    Sigma = np.diag([0.04, 0.09, 1.0, 1.0])
    mu = np.array([0.02, 0.02, 0.01, 0.0])
    r = solve_leaf_relaxed_exact(mu, Sigma)
    assert r.status == "slack"
    np.testing.assert_allclose(r.w, [0.09 / 0.13, 0.04 / 0.13, 0, 0], atol=1e-9)
