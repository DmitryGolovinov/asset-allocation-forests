"""How often does the convex relaxation change the optimal VALUE of the node problems a forest
actually meets? Both formulations evaluated on the SAME stored problems.

Predefined development node sample (French industries, development period only): the forests
refitted at the first development refit on or after 1970-01, 1990-01 and 2010-01 (expanding
window up to that month), seed 0, every tree, grown once with the paper's equality leaf and
once with the relaxed leaf. Every (mean, covariance) passed to the leaf solver during growth
is recorded. For each stored problem: the equality optimum (face enumeration), the relaxed
optimum, the solver's slack status (a <= v), the proposition's gap condition (v > b) and the
realized gap. Writes ``results/paired_value_gap.csv`` (one row per problem) and
``results/paired_value_gap_summary.json``. Development data only; no result is selected on it.

On binding problems the relaxed solver returns the equality solution (proposition (ii)), so the
agreement of condition and gap there is true by construction, not evidence. The checks that do
not rely on the solver's own branch logic are reported separately: the match of condition and gap
on the slack subset, where the relaxed value comes from the slack point and the equality value
from face enumeration; an independent interior-point solve of the relaxation (Clarabel via
cvxpy) on a fixed random sample of binding and slack problems; and, on tied faces, the minimum
variance a from Clarabel next to the exact KKT value. Problems within numerical resolution of the
proposition's boundary (best and second-best means within 1e-9, or v within 1e-9 of b) are
counted as unresolved instead of being classified.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aaf import forest as F  # noqa: E402
from aaf.leaf import (  # noqa: E402
    FastLeafSolver,
    _face_min_variance,
    ew_variance,
    solve_leaf_exact,
    solve_leaf_relaxed,
    solve_leaf_relaxed_exact,
)
from aaf.manifest import environment, tree_hash, write_manifest  # noqa: E402
from aaf.study import load_dataset  # noqa: E402

ORIGINS = ["1970-01-31", "1990-01-31", "2010-01-31"]
RESOLUTION = 1e-9  # mean differences and |v - b| / v below this are not classified
SAMPLE = {"binding": 3000, "slack": 1000}  # independent Clarabel solves, fixed seed 0
RECORD: list = []
_solve = FastLeafSolver.solve


def recording_solve(self, mu, Sigma):
    RECORD.append((self.formulation, np.array(mu, float), np.array(Sigma, float)))
    return _solve(self, mu, Sigma)


def face_range(mu, Sigma):
    top = float(mu.max())
    tied = mu >= top - 1e-14 * max(1.0, abs(top))
    M = np.flatnonzero(tied)
    S = Sigma[np.ix_(M, M)]
    w = _face_min_variance(S)
    second = float(mu[~tied].max()) if (~tied).any() else np.nan
    return float(w @ S @ w), float(np.diag(S).max()), top, len(M), top - second


def clarabel_min_variance(S):
    """Minimum variance on the simplex by an interior-point solver (independent of aaf.leaf)."""
    import cvxpy as cp

    w = cp.Variable(S.shape[0], nonneg=True)
    cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(S))), [cp.sum(w) == 1]).solve(
        solver=cp.CLARABEL
    )
    wv = np.maximum(np.asarray(w.value).ravel(), 0.0)
    wv /= wv.sum()
    return float(wv @ S @ wv)


def main() -> int:
    tic = time.perf_counter()
    cfg = yaml.safe_load((ROOT / "configs" / "study.yaml").read_text())
    Z, X, rf, first, last, _ = load_dataset(ROOT, cfg, "transfer_french5", "dev")
    dates = X.index
    Zv, Xv = Z.to_numpy(), X.to_numpy()
    FastLeafSolver.solve = recording_solve
    fits = []
    for o in ORIGINS:
        t = int(np.searchsorted(dates, pd.Timestamp(o)))
        for leaf in ("equality", "relaxed"):
            fcfg = dict(cfg["forest"], mtry=cfg["datasets"]["transfer_french5"]["mtry"], leaf=leaf)
            n0 = len(RECORD)
            t0 = time.perf_counter()
            F.fit_forest(Zv[:t], Xv[:t], fcfg, seed=0 * 1000 + t, n_jobs=1)
            fits.append(
                {
                    "origin": str(dates[t].date()),
                    "train_months": t,
                    "leaf": leaf,
                    "problems": len(RECORD) - n0,
                    "seconds": time.perf_counter() - t0,
                }
            )
            for k in range(n0, len(RECORD)):
                RECORD[k] = (*RECORD[k], str(dates[t].date()))
    FastLeafSolver.solve = _solve
    rows = []
    t1 = time.perf_counter()
    for form, mu, S, origin in RECORD:
        v = ew_variance(S)
        a, b, top, m, second_gap = face_range(mu, S)
        eq = solve_leaf_exact(mu, S)
        rx = solve_leaf_relaxed_exact(mu, S)
        gap = rx.objective - eq.objective
        scale = max(1.0, abs(top))
        near_tie = bool(m == 1 and second_gap <= RESOLUTION * scale)
        near_boundary = bool(abs(v - b) <= RESOLUTION * v)
        rows.append(
            {
                "origin": origin,
                "grown_with": form,
                "n_best_mean_assets": m,
                "v": v,
                "a": a,
                "a_clarabel": clarabel_min_variance(
                    S[np.ix_(*(2 * [np.flatnonzero(mu >= top - 1e-14 * scale)]))]
                )
                if m > 1
                else np.nan,
                "b": b,
                "best_minus_second_mean": second_gap,
                "slack_status": bool(a <= v * (1 + 1e-12)),
                "gap_condition_v_gt_b": bool(v > b * (1 + 1e-10)),
                "unresolved": near_tie or near_boundary,
                "value_eq": eq.objective,
                "value_rx": rx.objective,
                "gap": gap,
                "strict_gap": bool(gap > 1e-12 * scale),
                "eq_status": eq.status,
                "eq_feasibility_residual": eq.feasibility_residual,
            }
        )
    tab = pd.DataFrame(rows)
    t_eval = time.perf_counter()
    # independent interior-point solve of the relaxation on a fixed sample of each status
    rng = np.random.default_rng(0)
    tab["clarabel_sample"] = False
    tab["value_rx_clarabel"] = np.nan
    tab["var_rx_clarabel_rel"] = np.nan  # (w'Sigma w - v) / v at the Clarabel solution
    for status, n in SAMPLE.items():
        pool = np.flatnonzero(tab["slack_status"].to_numpy() == (status == "slack"))
        for i in np.sort(rng.choice(pool, size=min(n, pool.size), replace=False)):
            _, mu, S, _ = RECORD[i]
            ref = solve_leaf_relaxed(mu, S)
            v = ew_variance(S)
            tab.loc[i, ["clarabel_sample", "value_rx_clarabel", "var_rx_clarabel_rel"]] = [
                True,
                ref.objective,
                (float(ref.w @ S @ ref.w) - v) / v,
            ]
    t2 = time.perf_counter()
    out = ROOT / "results"
    tab.to_csv(out / "paired_value_gap.csv", index=False)
    summ = {
        "design": {
            "dataset": "transfer_french5 (development only)",
            "origins": ORIGINS,
            "seed": 0,
            "trees_per_forest": cfg["forest"]["n_trees"],
            "formulations_grown": ["equality", "relaxed"],
        },
        "fits": fits,
        "problems": int(len(tab)),
        "resolution": RESOLUTION,
        "clarabel_sample": SAMPLE,
        "evaluation_seconds": t_eval - t1,
        "clarabel_seconds": t2 - t_eval,
        "total_seconds": time.perf_counter() - tic,
        "by": {},
    }
    for key, g in [("all", tab)] + list(tab.groupby("grown_with")):
        match = g["gap_condition_v_gt_b"] == g["strict_gap"]
        slack, res = g["slack_status"], ~g["unresolved"]
        cs = g[g["clarabel_sample"]]
        csb, css = cs[~cs["slack_status"]], cs[cs["slack_status"]]
        tied = g[g["n_best_mean_assets"] > 1]
        summ["by"][key] = {
            "problems": int(len(g)),
            "slack_status_share": float(g["slack_status"].mean()),
            "strict_gap_share": float(g["strict_gap"].mean()),
            "slack_without_gap": int((g["slack_status"] & ~g["strict_gap"]).sum()),
            "gap_without_slack": int((~g["slack_status"] & g["strict_gap"]).sum()),
            # includes binding problems, where agreement holds by construction (see docstring)
            "condition_matches_gap": float(match.mean()),
            "slack_problems": int(slack.sum()),
            "unresolved_problems": int((~res).sum()),
            "condition_matches_gap_on_slack_resolved": float(match[slack & res].mean())
            if (slack & res).any()
            else None,
            "condition_mismatches_resolved": int((~match & res).sum()),
            "clarabel_binding_problems": int(len(csb)),
            "clarabel_slack_problems": int(len(css)),
            # > 0 would mean the relaxation beats the equality optimum on a binding problem
            "max_clarabel_minus_eq_on_binding": float(
                (csb["value_rx_clarabel"] - csb["value_eq"]).max()
            )
            if len(csb)
            else None,
            "max_abs_clarabel_minus_exact_rx": float(
                (cs["value_rx_clarabel"] - cs["value_rx"]).abs().max()
            )
            if len(cs)
            else None,
            "max_abs_clarabel_rel_var_gap_on_binding": float(csb["var_rx_clarabel_rel"].abs().max())
            if len(csb)
            else None,
            # interior-point solutions sit slightly inside the constraint; the largest shortfall
            # occurs where the best two means nearly tie (a nearly flat objective)
            "median_clarabel_rel_var_gap_on_binding": float(csb["var_rx_clarabel_rel"].median())
            if len(csb)
            else None,
            "best_minus_second_mean_at_max_clarabel_var_gap": float(
                csb.loc[csb["var_rx_clarabel_rel"].abs().idxmax(), "best_minus_second_mean"]
            )
            if len(csb)
            else None,
            "tied_best_mean_problems": int(len(tied)),
            "max_rel_a_kkt_minus_clarabel_tied": float(
                ((tied["a"] - tied["a_clarabel"]) / tied["v"]).max()
            )
            if len(tied)
            else None,
            "median_gap_bps_per_month_given_gap": float(
                1e4 * g.loc[g["strict_gap"], "gap"].median()
            )
            if g["strict_gap"].any()
            else None,
            "max_eq_feasibility_residual": float(g["eq_feasibility_residual"].max()),
        }
    (out / "paired_value_gap_summary.json").write_text(json.dumps(summ, indent=1))
    write_manifest(
        out / "paired_value_gap_manifest.json",
        {
            "study": "asset-allocation-forests / paired relaxation value gap (development forests)",
            "source_tree_sha256": tree_hash(ROOT),
            "environment": environment(("numpy", "pandas", "scipy", "cvxpy", "clarabel")),
            "command": "python scripts/paired_value_gap.py",
            "runtime_seconds": summ["total_seconds"],
        },
        [out / "paired_value_gap_summary.json", out / "paired_value_gap.csv"],
    )
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
