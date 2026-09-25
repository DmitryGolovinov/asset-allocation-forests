"""Leaf-solver and ex-ante risk diagnostics restricted to a run's scored months.

A final run walks forward continuously from the development start (1947-07 for the French
transfer) and scores only its final months, so the run-level ``diagnostics.json`` describes every
month and refit since the walk-forward start. This script recomputes the ex-ante volatility ratio
of the averaged forest portfolio for every month from the stored weights and each refit's
training covariance (the definition in ``aaf.backtest.walk_forward``), stops unless the
all-month recomputation reproduces the stored summary, and reports the statistics over the
scored months only, together with the refits whose forests produced those months' weights.
Writes ``results/<run>/evaluation_diagnostics.json`` and its manifest. Descriptive only: nothing
is refitted or selected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aaf.leaf import ew_variance  # noqa: E402
from aaf.manifest import environment, tree_hash, write_manifest  # noqa: E402
from aaf.study import load_dataset  # noqa: E402

RUNS = [
    "transfer_french5_dev",
    "transfer_french5_dev_relaxed",
    "transfer_french5_final",
    "transfer_french5_final_relaxed",
    "archival_hw3_dev",
    "archival_hw3_dev_relaxed",
]
STATS = ("count", "mean", "std", "min", "max")


def one(run: str) -> dict | None:
    res = ROOT / "results" / run
    man = json.loads((res / "manifest.json").read_text())
    seeds = man["seeds"]
    weights = [res / f"weights_AAF_seed{s}.parquet" for s in seeds]
    if not all(p.exists() for p in weights):
        print(f"skip {run}: per-month weights are not present (rerun the study to create them)")
        return None
    cfg = yaml.safe_load((ROOT / "configs" / "study.yaml").read_text())
    try:
        _, X, _, first, last, _ = load_dataset(ROOT, cfg, man["dataset"], man["mode"])
    except FileNotFoundError as e:
        print(f"skip {run}: input data missing ({e})")
        return None
    ev = man["evaluation"]
    dates, Xv = X.index, X.to_numpy()
    t0 = int(np.searchsorted(dates, first))
    t1 = int(np.searchsorted(dates, last, side="right"))
    every = int(cfg["forest"]["refit_months"])
    diag = json.loads((res / "diagnostics.json").read_text())
    out = {"run": run, "evaluation": ev, "refit_months": every, "seeds": {}}
    for s, wp in zip(seeds, weights, strict=True):
        W = pd.read_parquet(wp)
        if not W.index.equals(dates[t0:t1]):
            raise SystemExit(f"{run} seed {s}: stored weights do not match the walk-forward dates")
        cov, ratio = {}, []
        for i, t in enumerate(range(t0, t1)):
            tr = t0 + ((t - t0) // every) * every  # the refit whose forest set month t
            if tr not in cov:
                cov[tr] = np.cov(Xv[:tr], rowvar=False)
            S, w = cov[tr], W.iloc[i].to_numpy()
            ratio.append(float(np.sqrt(w @ S @ w / ew_variance(S))))
        r = pd.Series(ratio, index=W.index)
        stored = diag[str(s)]["aaf_exante_vol_ratio"]
        full = r.describe()
        for k in STATS:
            if abs(full[k] - stored[k]) > 1e-12 * max(1.0, abs(stored[k])):
                raise SystemExit(f"{run} seed {s}: recomputed {k} {full[k]} != stored {stored[k]}")
        scored = r.loc[ev["first"] : ev["last"]]
        if len(scored) != ev["months"]:
            raise SystemExit(f"{run} seed {s}: {len(scored)} scored months, not {ev['months']}")
        used = {
            str(dates[t0 + ((t - t0) // every) * every].date())
            for t in range(t0, t1)
            if pd.Timestamp(ev["first"]) <= dates[t] <= pd.Timestamp(ev["last"])
        }
        rf = pd.DataFrame(diag[str(s)]["refits"])
        rf = rf[rf["refit"].isin(used)]
        if len(rf) != len(used):
            raise SystemExit(f"{run} seed {s}: refit records missing for scored months")
        out["seeds"][str(s)] = {
            "exante_vol_ratio_scored_months": {k: float(scored.describe()[k]) for k in STATS},
            "exante_vol_ratio_all_months_matches_stored": True,
            "refits_used_for_scored_months": sorted(used),
            "leaf_solves": int(rf["leaf_solves"].sum()),
            "exact_path_fallbacks": int(rf["leaf_fallbacks"].sum()),
            "slack_leaf_solves": int(rf["slack_leaf_solves"].sum()),
            "max_abs_global_objective_minus_multistart_ref": float(
                rf["global_ref_gap"].abs().max()
            ),
            "max_global_feasibility_residual": float(rf["global_feas_resid"].max()),
            "max_relaxed_minus_equality_global_objective": float(rf["global_relaxed_gap"].max()),
            "min_relaxed_var_over_ew_var": float(rf["global_relaxed_var_ratio"].min()),
            "max_cond_train_cov": float(rf["cond_train_cov"].max()),
        }
    path = res / "evaluation_diagnostics.json"
    path.write_text(json.dumps(out, indent=1))
    write_manifest(
        res / "evaluation_diagnostics_manifest.json",
        {
            "study": f"asset-allocation-forests / scored-month diagnostics of {run}",
            "source_tree_sha256": tree_hash(ROOT),
            "environment": environment(("numpy", "pandas")),
            "command": f"python scripts/evaluation_diagnostics.py {run}",
            "inputs": {"run_manifest_source_tree": man["source_tree_sha256"]},
        },
        [path],
    )
    print(f"wrote {path.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    for run in sys.argv[1:] or RUNS:
        if (ROOT / "results" / run / "manifest.json").exists():
            one(run)
