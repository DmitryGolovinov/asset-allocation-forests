"""Reproducible benchmark of the leaf solvers on deterministic problem families.

Families (fixed seeds): well-conditioned random covariances, near-singular (rank-deficient plus
1e-10 ridge), a duplicated asset (singular), a zero-variance asset, two tied best means, and a
unique best asset exactly on the risk boundary (Sigma_ii = v). Dimensions N = 2-6 and 8 (20
instances per family each) and N = 10 (5 per family, to show the exponential face count): 750.

Methods: exact equality solver (face enumeration, ``solve_leaf_exact``); exact relaxed solver
(``solve_leaf_relaxed_exact``); cvxpy/Clarabel on the relaxation (``solve_leaf_relaxed``);
multistart SLSQP on the equality problem (``solve_leaf_reference``, a local method: no global
certificate); the batched ``FastLeafSolver`` used inside the forest.

Per instance: objective values, feasibility residuals, simplex residuals, the gaps exact minus
SLSQP (a negative value would mean enumeration missed a better feasible point) and exact
relaxed minus cvxpy, runtimes, the covariance condition number and every status.
Writes results/leaf_benchmark.csv and reports/leaf_benchmark.md.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aaf.leaf import (  # noqa: E402
    FastLeafSolver,
    ew_variance,
    solve_leaf_exact,
    solve_leaf_reference,
    solve_leaf_relaxed,
    solve_leaf_relaxed_exact,
)
from aaf.manifest import environment, tree_hash, write_manifest  # noqa: E402

FAMILIES = ["random", "near_singular", "duplicate", "zero_variance", "tied_means", "boundary"]


def instance(family: str, n: int, rng: np.random.Generator):
    vols = rng.uniform(0.02, 0.07, n)
    A = rng.normal(size=(n, n))
    C = np.corrcoef(A @ rng.normal(size=(n, 3 * n)))
    S = C * np.outer(vols, vols)
    mu = rng.normal(0.005, 0.004, n)
    if family == "near_singular" and n >= 3:
        B = rng.normal(size=(n, max(1, n // 2))) * 0.03
        S = B @ B.T + 1e-10 * np.eye(n)
    elif family == "duplicate" and n >= 2:
        S[-1, :], S[:, -1] = S[0, :], S[:, 0]
        S[-1, -1] = S[0, 0]
        mu[-1] = mu[0] - 1e-4
    elif family == "zero_variance":
        S[-1, :] = S[:, -1] = 0.0
    elif family == "tied_means" and n >= 2:
        k = rng.choice(n, 2, replace=False)
        mu[k] = mu.max() + 0.002
    elif family == "boundary":
        i = int(np.argmax(mu))
        c = (S.sum() - S[i, i]) / n**2
        S[i, i] = c / (1 - 1 / n**2)  # fixed point: S_ii = e'Se / n^2
        if np.linalg.eigvalsh(S)[0] <= 1e-10:
            return None
    return mu, 0.5 * (S + S.T)


def timed(f, *a, **k):
    t = time.perf_counter()
    r = f(*a, **k)
    return r, 1e3 * (time.perf_counter() - t)


def main() -> int:
    tic = time.perf_counter()
    rows = []
    for n in [2, 3, 4, 5, 6, 8, 10]:
        reps = 5 if n == 10 else 20
        fast = FastLeafSolver(n, "equality")
        fast_rx = FastLeafSolver(n, "relaxed")
        for fam in FAMILIES:
            rng = np.random.default_rng(1000 * n + FAMILIES.index(fam))
            k = 0
            while k < reps:
                inst = instance(fam, n, rng)
                if inst is None:
                    continue
                k += 1
                mu, S = inst
                v = ew_variance(S)
                ev = np.linalg.eigvalsh(S)
                eq, t_eq = timed(solve_leaf_exact, mu, S)
                rx, t_rx = timed(solve_leaf_relaxed_exact, mu, S)
                cv, t_cv = timed(solve_leaf_relaxed, mu, S)
                ref, t_ref = timed(solve_leaf_reference, mu, S, starts=20, seed=k)
                (wf, _), t_f = timed(fast.solve, mu, S)
                (wr, _), t_fr = timed(fast_rx.solve, mu, S)
                rows.append(
                    {
                        "n": n,
                        "family": fam,
                        "instance": k,
                        "faces": 2**n - 1,
                        "cond": float(ev[-1] / max(ev[0], 1e-300)),
                        "eq_objective": eq.objective,
                        "eq_status": eq.status,
                        "eq_feasibility_residual": eq.feasibility_residual,
                        "eq_simplex_residual": float(abs(eq.w.sum() - 1) + max(0.0, -eq.w.min())),
                        "slsqp_objective": ref.objective,
                        "slsqp_status": ref.status,
                        "slsqp_feasibility_residual": ref.feasibility_residual,
                        "exact_minus_slsqp": eq.objective - ref.objective,
                        "rx_objective": rx.objective,
                        "rx_status": rx.status,
                        "rx_excess_variance": max(0.0, float(rx.w @ S @ rx.w) - v) / v,
                        "cvxpy_objective": cv.objective,
                        "rx_minus_cvxpy": rx.objective - cv.objective,
                        "fast_eq_minus_exact": float(mu @ wf) - eq.objective,
                        "fast_eq_feasibility_residual": abs(float(wf @ S @ wf) - v) / v,
                        "fast_rx_minus_exact": float(mu @ wr) - rx.objective,
                        "ms_exact_eq": t_eq,
                        "ms_exact_rx": t_rx,
                        "ms_cvxpy": t_cv,
                        "ms_slsqp_20_starts": t_ref,
                        "ms_fast_eq": t_f,
                        "ms_fast_rx": t_fr,
                    }
                )
    tab = pd.DataFrame(rows)
    tab.to_csv(ROOT / "results" / "leaf_benchmark.csv", index=False)
    g = tab.groupby(["n", "family"])
    summ = pd.DataFrame(
        {
            "instances": g.size(),
            "max_eq_feas_resid": g["eq_feasibility_residual"].max(),
            "min_exact_minus_slsqp": g["exact_minus_slsqp"].min(),
            "slsqp_worse_share": g["exact_minus_slsqp"].apply(lambda x: float((x > 1e-8).mean())),
            "max_abs_rx_minus_cvxpy": g["rx_minus_cvxpy"].apply(lambda x: float(np.abs(x).max())),
            "max_abs_fast_minus_exact": g["fast_eq_minus_exact"].apply(
                lambda x: float(np.abs(x).max())
            ),
            "eq_status": g["eq_status"].apply(
                lambda x: ", ".join(f"{k} {v}" for k, v in x.value_counts().items())
            ),
            "median_ms_exact": g["ms_exact_eq"].median(),
            "median_ms_slsqp": g["ms_slsqp_20_starts"].median(),
            "max_cond": g["cond"].max(),
        }
    ).reset_index()
    by_n = (
        tab.groupby("n")
        .agg(
            faces=("faces", "first"),
            median_ms_exact=("ms_exact_eq", "median"),
            median_ms_fast=("ms_fast_eq", "median"),
            median_ms_slsqp=("ms_slsqp_20_starts", "median"),
            median_ms_cvxpy=("ms_cvxpy", "median"),
        )
        .reset_index()
    )
    L = [
        "# Leaf-solver benchmark",
        "",
        "Generated by `scripts/leaf_benchmark.py` (deterministic seeds; runtimes are wall-clock on the "
        "machine that ran it and indicative only). Equality problem: maximize mu'w subject to "
        "w'Sigma w = v (equal-weight variance), 1'w = 1, w >= 0; relaxed: variance at most v.",
        "",
        "Exact enumeration visits all 2^N - 1 faces: it is exact for these sizes and exponential in "
        "N, not a method for hundreds of assets. SLSQP is a local method with random restarts and "
        "gives no global certificate; a positive `exact - SLSQP` gap means enumeration found a better "
        "feasible point than every restart, a negative one would be an enumeration failure.",
        "",
        "| N | family | instances | max equality feasibility residual | min exact - SLSQP | share where SLSQP is worse | max abs relaxed - cvxpy | max abs batched - exact | equality statuses | median ms exact | median ms SLSQP x20 | max condition number |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for _, r in summ.iterrows():
        L.append(
            f"| {r['n']} | {r['family']} | {r['instances']} | {r['max_eq_feas_resid']:.1e} | "
            f"{r['min_exact_minus_slsqp']:+.1e} | {r['slsqp_worse_share']:.2f} | "
            f"{r['max_abs_rx_minus_cvxpy']:.1e} | {r['max_abs_fast_minus_exact']:.1e} | "
            f"{r['eq_status']} | {r['median_ms_exact']:.2f} | {r['median_ms_slsqp']:.1f} | "
            f"{r['max_cond']:.1e} |"
        )
    L += [
        "",
        "Runtime against dimension (median over all families):",
        "",
        "| N | faces | exact (ms) | batched forest solver (ms) | SLSQP x20 (ms) | cvxpy relaxed (ms) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in by_n.iterrows():
        L.append(
            f"| {r['n']} | {r['faces']} | {r['median_ms_exact']:.2f} | {r['median_ms_fast']:.2f} | "
            f"{r['median_ms_slsqp']:.1f} | {r['median_ms_cvxpy']:.1f} |"
        )
    L.append("")
    (ROOT / "reports" / "leaf_benchmark.md").write_text("\n".join(L))
    write_manifest(
        ROOT / "results" / "leaf_benchmark_manifest.json",
        {
            "study": "asset-allocation-forests / leaf-solver benchmark (synthetic instances)",
            "source_tree_sha256": tree_hash(ROOT),
            "environment": environment(("numpy", "scipy", "cvxpy", "clarabel")),
            "command": "python scripts/leaf_benchmark.py",
            "runtime_seconds": time.perf_counter() - tic,
            "note": "runtimes are wall-clock on the machine that ran it and indicative only",
        },
        [ROOT / "results" / "leaf_benchmark.csv"],
    )
    print(summ.to_string())
    print(by_n.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
