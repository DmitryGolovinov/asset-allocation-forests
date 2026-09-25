"""Leaf portfolio problem of the Asset Allocation Forest (paper eq. 2 with lambda = 0).

Exact problem (EQUALITY, nonconvex feasible set)::

    maximize    mu'w
    subject to  w' Sigma w = v,   1'w = 1,   w >= 0,        v = sigma_EW^2 = e'Sigma e / N^2

with mu the mean EXCESS return and Sigma the covariance of excess returns in the leaf. Because
the volatility is pinned to sigma_EW, maximizing the Sharpe ratio (mu'w)/sqrt(w'Sigma w) on the
feasible set is the same as maximizing mu'w.

Solution method: the optimum lies in the relative interior of some face
F_S = {w_S > 0, w_{not S} = 0}. On the affine hull of a face the problem is an equality
constrained quadratic program with the closed form (derived in docs/methodology.md)

    w(a) = w_mv + (1 / 2a) Sigma_S^{-1} (mu_S - (c1/c2) 1),     w_mv = Sigma_S^{-1} 1 / c2
    var  = 1/c2 + D / (4 a^2),   D = c3 - c1^2/c2 >= 0,   a = +1/2 sqrt(D / (v - 1/c2))

where c1 = 1'S^-1 mu, c2 = 1'S^-1 1, c3 = mu'S^-1 mu (S = Sigma_S); a > 0 is the maximizer.
Enumerating all 2^N - 1 faces and keeping the feasible candidate with the largest mu'w gives
the global optimum for small N (N = 5 here), because the maximum of a linear function on the
face's ellipsoidal slice is attained either at this critical point or on a lower face.

Degenerate faces with D = 0 (mu_S constant in the Sigma metric, e.g. equal means) have a
constant objective; such a face is optimal iff it contains a feasible point, which exists iff
min_var(F_S) <= v <= max_i Sigma_ii (intermediate value theorem on the connected polytope).
The notebook skipped these faces; we construct a point on the segment between the face's
minimum-variance portfolio and its highest-variance vertex.

The CONVEX RELAXATION (w'Sigma w <= v) is a different problem and is exposed separately.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from scipy.linalg import cho_factor, cho_solve


@dataclass
class LeafResult:
    w: np.ndarray
    objective: float  # mu'w (monthly mean excess return)
    sr: float  # objective / sqrt(w'Sigma w)
    feasibility_residual: float  # |w'Sigma w - v| / v
    status: str  # "ok", "degenerate_face", "fallback_ew"
    faces_tried: int = 0
    cond: float = np.nan
    extras: dict = field(default_factory=dict)


def ew_variance(Sigma: np.ndarray) -> float:
    n = Sigma.shape[0]
    e = np.full(n, 1.0 / n)
    return float(e @ Sigma @ e)


def _face_min_variance(S: np.ndarray) -> np.ndarray:
    """Exact minimum-variance point of the simplex spanned by a (small) face.

    Convex QP min w'Sw s.t. 1'w = 1, w >= 0. Some optimal solution is a vertex of the optimal
    set; on its support T the stationarity system 2 S_T w_T = nu 1, 1'w_T = 1 has a nonsingular
    matrix (S is positive semidefinite) and a nonnegative solution. So the optimum is among the
    nonnegative stationary points of the 2^k - 1 supports: each is solved by least squares, and
    every candidate is a feasible portfolio whose variance is evaluated directly, so the minimum
    over candidates needs no dual (multiplier) tolerance, which is unreliable on near-singular
    faces. Ties within a relative 1e-13 keep the smaller support. Exponential in the face size;
    faces here have at most the number of assets (five in the studies). Replaces a
    projected-gradient routine capped at 5,000 steps that was inaccurate on near-singular faces
    (tests/test_relaxed_theorem.py)."""
    k = S.shape[0]
    if k == 1:
        return np.ones(1)
    best, best_v = None, np.inf
    for size in range(1, k + 1):
        for T in itertools.combinations(range(k), size):
            idx = list(T)
            A = np.zeros((size + 1, size + 1))
            A[:size, :size] = 2 * S[np.ix_(idx, idx)]
            A[:size, size] = -1.0
            A[size, :size] = 1.0
            rhs = np.zeros(size + 1)
            rhs[size] = 1.0
            wT = np.linalg.lstsq(A, rhs, rcond=None)[0][:size]
            if not np.isfinite(wT).all() or wT.min() < -1e-9 or wT.sum() <= 0:
                continue
            w = np.zeros(k)
            w[idx] = np.maximum(wT, 0.0)
            w /= w.sum()
            val = float(w @ S @ w)
            if best is None or val < best_v - 1e-13 * abs(best_v):
                best, best_v = w, val
    if best is None:  # cannot happen: every single-asset support is a feasible candidate
        raise RuntimeError("no candidate for the face minimum-variance problem")
    return best


def _proj_simplex(v: np.ndarray) -> np.ndarray:
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - 1
    k = np.arange(1, v.size + 1)
    rho = k[u - css / k > 0][-1]
    return np.maximum(v - css[rho - 1] / rho, 0)


def solve_leaf_exact(
    mu: np.ndarray, Sigma: np.ndarray, v: float | None = None, tol: float = 1e-10
) -> LeafResult:
    """Global optimum of the equality problem by face enumeration (N <= ~10)."""
    n = mu.size
    Sigma = 0.5 * (Sigma + Sigma.T)
    v = ew_variance(Sigma) if v is None else float(v)
    best: tuple[float, np.ndarray, str] | None = None
    tried = 0
    for k in range(1, n + 1):
        for S in itertools.combinations(range(n), k):
            tried += 1
            S = list(S)
            SS, mS = Sigma[np.ix_(S, S)], mu[S]
            for wS, status in _face_candidates(SS, mS, v, tol):
                w = np.zeros(n)
                w[S] = wS
                obj = float(mu @ w)
                if best is None or obj > best[0] + 1e-15:
                    best = (obj, w, status)
    evals = np.linalg.eigvalsh(Sigma)
    cond = float(evals[-1] / max(evals[0], 1e-300))
    if best is None:  # cannot happen when v = sigma_EW^2 (EW is feasible); kept explicit
        w = np.full(n, 1.0 / n)
        return LeafResult(
            w,
            float(mu @ w),
            _sr(mu, Sigma, w),
            abs(w @ Sigma @ w - v) / v,
            "fallback_ew",
            tried,
            cond,
        )
    obj, w, status = best
    return LeafResult(
        w, obj, _sr(mu, Sigma, w), abs(float(w @ Sigma @ w) - v) / v, status, tried, cond
    )


def _sr(mu, Sigma, w) -> float:
    var = float(w @ Sigma @ w)
    return float(mu @ w) / np.sqrt(var) if var > 0 else 0.0


def _hull_basis(k: int) -> np.ndarray:
    """Orthonormal basis (k x k-1) of the directions d with 1'd = 0."""
    B = np.eye(k)[:, :-1] - np.eye(k)[:, [-1]]
    Q, _ = np.linalg.qr(B)
    return Q


def _face_candidates(S: np.ndarray, m: np.ndarray, v: float, tol: float) -> list:
    """Feasible critical points of mu'w on {1'w = 1, w'Sw = v} within one face.

    The face's affine hull is parameterized as w = e/k + N z with N an orthonormal basis of
    {d : 1'd = 0}. Then var = c0 + 2 g'z + z'Az (A = N'SN, g = N'S e/k, c0 = e'S e/k^2) and the
    objective is mu'e/k + b'z (b = N'mu). If A is positive definite the level set is an
    ellipsoid centred at z* = -A^{-1}g with minimum variance c0 - g'A^{-1}g, and the critical
    points of the linear objective are z = z* +/- sqrt(r / b'A^{-1}b) A^{-1}b, r = v - min var.

    This needs A (the covariance restricted to the hull), not S itself, to be invertible.
    The previous Cholesky-of-S version skipped every face containing, e.g., a zero-variance
    asset even though A was positive definite there, and could miss the optimum (review
    counterexample, tests/test_review_regressions.py). If A is singular, a null direction d
    has d'Sd = 0, hence S d = 0: variance is constant along d while the objective changes by
    t mu'd, so an equal or better feasible point lies on a lower face and skipping is exact.

    Both roots are returned when feasible: on a two-asset face the equality set is exactly the
    two points, and the "minimizing" root can be the only feasible one.
    """
    k = m.size
    if k == 1:
        return [(np.ones(1), "ok")] if abs(S[0, 0] - v) <= tol * max(v, 1e-300) else []
    N = _hull_basis(k)
    e0 = np.full(k, 1.0 / k)
    A = N.T @ S @ N
    A = 0.5 * (A + A.T)
    ev = np.linalg.eigvalsh(A)
    if ev[0] <= 1e-12 * max(ev[-1], 1e-300):
        return []  # singular on the hull: covered exactly by lower faces (see docstring)
    cf = cho_factor(A, lower=True, check_finite=True)
    g = N.T @ S @ e0
    b = N.T @ m
    z_star = -cho_solve(cf, g)
    min_var = float(e0 @ S @ e0 + g @ z_star)
    Ab = cho_solve(cf, b)
    q = float(b @ Ab)
    if q <= 1e-12 * max(float(np.abs(m).max()) ** 2 / max(ev[-1], 1e-300), 1e-300):
        pt = _degenerate_face_point(S, v, tol)  # mu constant on the face: objective constant
        return [pt] if pt is not None else []
    if v < min_var * (1 - tol):
        return []
    r = max(v - min_var, 0.0)
    step = np.sqrt(r / q) * Ab
    roots = [z_star] if r <= tol * max(v, 1e-300) else [z_star + step, z_star - step]
    out = []
    for z in roots:
        wS = e0 + N @ z
        if wS.min() >= -1e-12:
            wS = np.maximum(wS, 0.0)
            out.append((wS / wS.sum(), "ok"))
    return out


def _degenerate_face_point(S: np.ndarray, v: float, tol: float):
    """Feasible point on a face with constant objective, or None if none exists."""
    w_min = _face_min_variance(S)
    vmin = float(w_min @ S @ w_min)
    j = int(np.argmax(np.diag(S)))
    vmax = float(S[j, j])
    if v < vmin * (1 - tol) or v > vmax * (1 + tol):
        return None
    e = np.zeros_like(w_min)
    e[j] = 1.0
    d = e - w_min
    # var(t) = vmin + 2t w_min'S d + t^2 d'S d, solve var(t) = v for t in [0, 1].
    A, B, C = float(d @ S @ d), 2.0 * float(w_min @ S @ d), vmin - v
    if A <= 0:
        t = 0.0
    else:
        disc = max(B * B - 4 * A * C, 0.0)
        t = (-B + np.sqrt(disc)) / (2 * A)
    t = float(np.clip(t, 0.0, 1.0))
    return w_min + t * d, "degenerate_face"


def solve_leaf_relaxed(mu: np.ndarray, Sigma: np.ndarray, v: float | None = None) -> LeafResult:
    """Convex relaxation: maximize mu'w s.t. w'Sigma w <= v (a DIFFERENT formulation)."""
    import cvxpy as cp

    n = mu.size
    Sigma = 0.5 * (Sigma + Sigma.T)
    v = ew_variance(Sigma) if v is None else float(v)
    w = cp.Variable(n, nonneg=True)
    prob = cp.Problem(
        cp.Maximize(mu @ w), [cp.sum(w) == 1, cp.quad_form(w, cp.psd_wrap(Sigma)) <= v]
    )
    prob.solve(solver=cp.CLARABEL)
    wv = np.maximum(np.asarray(w.value).ravel(), 0)
    wv /= wv.sum()
    return LeafResult(
        wv,
        float(mu @ wv),
        _sr(mu, Sigma, wv),
        max(float(wv @ Sigma @ wv) - v, 0.0) / v,
        prob.status,
    )


def solve_leaf_relaxed_exact(
    mu: np.ndarray, Sigma: np.ndarray, v: float | None = None, tol: float = 1e-10
) -> LeafResult:
    """Exact solution of the convex relaxation  max mu'w  s.t.  w'Sigma w <= v, 1'w = 1, w >= 0.

    Let M be the set of assets with the largest mean mu*, F_M their face, a and b the smallest
    and largest variance on F_M (b = max over M of Sigma_ii). (i) If a <= v (for a single asset:
    Sigma_ii <= v), the minimum-variance point of F_M is optimal with value mu*, because
    mu'w <= mu* on the simplex; this is the "slack" branch. (ii) Otherwise the constraint binds
    at every optimum: an optimum w* with w*'Sigma w* < v would be a local, hence (linear
    objective, convex set) global, maximizer of mu'w on the simplex, i.e. a point of F_M with
    variance < v, which does not exist. A binding optimum is feasible for the equality problem,
    whose feasible set is contained in the relaxed one, so the two optimal values and optimizer
    sets coincide and the equality solution (``solve_leaf_exact``) solves the relaxation.
    (iii) The equality value equals mu* iff a <= v <= b, so the relaxed value is strictly
    higher iff v > b. The slack branch is therefore not the same as a value gap: tied top means
    with a <= v <= b, or a unique top asset with Sigma_ii = v, give slack without a gap. Among
    slack optima the minimum-variance point is chosen: a deterministic rule, which also
    maximizes the Sharpe ratio when the top mean is positive. ``solve_leaf_relaxed`` (cvxpy) is
    a separate numerical check. Proof and counterexamples: docs/methodology.md."""
    Sigma = 0.5 * (Sigma + Sigma.T)
    v = ew_variance(Sigma) if v is None else float(v)
    slack = _relaxed_slack_point(mu, Sigma, v)
    if slack is not None:
        w = slack
        return LeafResult(
            w,
            float(mu @ w),
            _sr(mu, Sigma, w),
            max(float(w @ Sigma @ w) - v, 0.0) / v,
            "slack",
            0,
        )
    r = solve_leaf_exact(mu, Sigma, v, tol)
    r.status = "binding_" + r.status
    return r


def _relaxed_slack_point(mu: np.ndarray, Sigma: np.ndarray, v: float) -> np.ndarray | None:
    top = float(mu.max())
    tied = np.flatnonzero(mu >= top - 1e-14 * max(1.0, abs(top)))
    n = mu.size
    if tied.size == 1:
        i = int(tied[0])
        if Sigma[i, i] <= v * (1 + 1e-12):
            return np.eye(n)[i]
        return None
    S = Sigma[np.ix_(tied, tied)]
    wt = _face_min_variance(S)
    if float(wt @ S @ wt) <= v * (1 + 1e-12):
        w = np.zeros(n)
        w[tied] = wt
        return w
    return None


def solve_leaf_reference(
    mu: np.ndarray, Sigma: np.ndarray, v: float | None = None, starts: int = 30, seed: int = 0
) -> LeafResult:
    """Independent numerical reference: multistart SLSQP on the equality problem.

    A cross-check only: local solutions give no global certificate."""
    from scipy.optimize import minimize

    n = mu.size
    v = ew_variance(Sigma) if v is None else float(v)
    rng = np.random.default_rng(seed)
    cons = [
        {"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)},
        {
            "type": "eq",
            "fun": lambda w: (w @ Sigma @ w - v) / v,
            "jac": lambda w: 2 * Sigma @ w / v,
        },
    ]
    best = None
    for i in range(starts):
        x0 = np.full(n, 1.0 / n) if i == 0 else rng.dirichlet(np.ones(n))
        r = minimize(
            lambda w: -mu @ w,
            x0,
            jac=lambda w: -mu,
            method="SLSQP",
            bounds=[(0, 1)] * n,
            constraints=cons,
            options={"ftol": 1e-14, "maxiter": 500},
        )
        w = np.clip(r.x, 0, None)
        w /= w.sum()
        feas = abs(w @ Sigma @ w - v) / v
        if feas < 1e-6 and (best is None or mu @ w > mu @ best):
            best = w
    if best is None:
        best = np.full(n, 1.0 / n)
    return LeafResult(
        best, float(mu @ best), _sr(mu, Sigma, best), abs(best @ Sigma @ best - v) / v, "reference"
    )


def legacy_solver(R: np.ndarray, rf: np.ndarray, ridge: float = 1e-6):
    """The original notebook's solver, kept verbatim in logic for regression comparison:
    covariance of TOTAL returns plus ridge, explicit inverse, equal-mean faces skipped."""
    import math

    T, N = R.shape
    mu = (R - rf[:, None]).mean(axis=0)
    Sigma = np.cov(R, rowvar=False) + ridge * np.eye(N)
    w_eq = np.ones(N) / N
    var_target = float(w_eq @ Sigma @ w_eq)
    best = None
    for k in range(1, N + 1):
        for S in itertools.combinations(range(N), k):
            S = list(S)
            try:
                A = np.linalg.inv(Sigma[np.ix_(S, S)])
            except np.linalg.LinAlgError:
                continue
            e = np.ones(k)
            c1, c2, c3 = float(e @ A @ mu[S]), float(e @ A @ e), float(mu[S] @ A @ mu[S])
            if c2 <= 0:
                continue
            min_var = 1.0 / c2
            if var_target <= min_var + 1e-12:
                if abs(var_target - min_var) > 1e-8:
                    continue
                wS = (A @ e) / c2
            else:
                numer = max(c3 - c1**2 / c2, 0.0)
                a = 0.5 * math.sqrt(numer / (var_target - 1.0 / c2))
                if not np.isfinite(a) or a <= 0:
                    continue
                b = (c1 - 2 * a) / c2
                wS = (A @ (mu[S] - b * e)) / (2 * a)
            if np.min(wS) < -1e-8:
                continue
            w = np.zeros(N)
            w[S] = np.maximum(wS, 0.0)
            w /= w.sum()
            ex = float(mu @ w)
            if best is None or ex > best[0]:
                best = (ex, w)
    return (np.ones(N) / N) if best is None else best[1]


class FastLeafSolver:
    """Batched version of :func:`solve_leaf_exact` for a fixed number of assets.

    All faces of equal size are solved in one batched ``numpy.linalg.solve`` call. Leaves that
    hit a degenerate or singular face are re-solved with the exact reference path, and those
    events are counted (``self.fallbacks``). Parity with the exact solver is a unit test.
    """

    def __init__(self, n: int, formulation: str = "equality"):
        if formulation not in ("equality", "relaxed"):
            raise ValueError(formulation)
        self.n = n
        self.formulation = formulation
        self.slack = 0  # relaxed leaves whose risk constraint is slack (best-mean asset)
        self.groups = []
        for k in range(1, n + 1):
            faces = np.array(list(itertools.combinations(range(n), k)))
            self.groups.append(faces)
        self.fallbacks = 0
        self.calls = 0

    def solve(self, mu: np.ndarray, Sigma: np.ndarray) -> tuple[np.ndarray, float]:
        """Returns (weights, Sharpe ratio). Equality: the Sharpe ratio at the EW volatility.
        Relaxed: see ``solve_leaf_relaxed_exact``; a slack solution reports its own Sharpe
        ratio, a binding one coincides with the equality solution."""
        self.calls += 1
        n = self.n
        v = ew_variance(Sigma)
        if self.formulation == "relaxed":
            w = _relaxed_slack_point(mu, Sigma, v)
            if w is not None:
                self.slack += 1
                return w, _sr(mu, Sigma, w)
        ev = np.linalg.eigvalsh(Sigma)
        if ev[0] <= 1e-8 * max(ev[-1], 1e-300):
            # Ill-conditioned or singular leaf covariance (condition number above 1e8): the
            # batched solves on Sigma_S lose accuracy there (audit: |var/v - 1| up to 4e-7 between
            # 1e8 and 1e10), so use the exact hull-coordinate path (counted as fallback).
            return self._exact(mu, Sigma)
        best_obj, best_w = -np.inf, None
        for faces in self.groups:
            k = faces.shape[1]
            if k == 1:
                for (i,) in faces:
                    if abs(Sigma[i, i] - v) <= 1e-10 * v and mu[i] > best_obj:
                        best_obj, best_w = mu[i], np.eye(n)[i]
                continue
            S = Sigma[faces[:, :, None], faces[:, None, :]]  # (F, k, k)
            m = mu[faces]  # (F, k)
            rhs = np.stack([m, np.ones_like(m)], axis=2)  # (F, k, 2)
            try:
                x = np.linalg.solve(S, rhs)
            except np.linalg.LinAlgError:
                return self._exact(mu, Sigma)
            x_mu, x_1 = x[..., 0], x[..., 1]
            c1 = x_mu.sum(axis=1)
            c2 = x_1.sum(axis=1)
            c3 = (m * x_mu).sum(axis=1)
            if np.any(c2 <= 0):
                return self._exact(mu, Sigma)
            D = c3 - c1 * c1 / c2
            if np.any(D <= 1e-12 * np.maximum(np.abs(c3), 1e-300)):
                return self._exact(mu, Sigma)  # degenerate face somewhere: exact path
            min_var = 1.0 / c2
            ok = v >= min_var * (1 - 1e-10)
            gap = np.maximum(v - min_var, 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                inv2a = np.where(gap > 0, np.sqrt(gap / D), 0.0)  # 1/(2a)
            base = x_1 / c2[:, None]
            step = inv2a[:, None] * (x_mu - (c1 / c2)[:, None] * x_1)
            for wS in (base + step, base - step):  # both roots, see _face_candidates
                okr = ok & (wS.min(axis=1) >= -1e-12)
                if not okr.any():
                    continue
                obj = np.where(okr, (m * wS).sum(axis=1), -np.inf)
                j = int(np.argmax(obj))
                if obj[j] > best_obj + 1e-15:
                    w = np.zeros(n)
                    w[faces[j]] = np.maximum(wS[j], 0.0)
                    best_obj, best_w = obj[j], w / w.sum()
        if best_w is None:
            return self._exact(mu, Sigma)
        return best_w, float(best_obj / np.sqrt(v))

    def _exact(self, mu, Sigma):
        self.fallbacks += 1
        r = solve_leaf_exact(mu, Sigma)
        return r.w, r.objective / np.sqrt(ew_variance(Sigma))
