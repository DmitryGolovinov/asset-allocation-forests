"""AAF study runner: archival reproduction and the French-industry transfer."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .backtest import (
    block_bootstrap_sr_diff,
    break_even_cost,
    choose_on_past,
    metrics,
    portfolio_path,
    walk_forward,
)
from .data import french_design, hw3_design, load_french, load_hw3
from .manifest import environment, git_commit, sha256_file, tree_hash, write_manifest

PACKAGES = ("numpy", "pandas", "scipy", "cvxpy", "joblib", "openpyxl")


class ReservedSampleError(RuntimeError):
    pass


def load_dataset(root: Path, cfg: dict, name: str, mode: str):
    d = cfg["datasets"][name]
    if name == "archival_hw3":
        Z, X, rf = hw3_design(load_hw3(root / d["path"]))
        return Z, X, rf, pd.Timestamp(d["first_oos"]), pd.Timestamp(d["last_oos"]), None
    ind, rf = load_french(root / "data")
    if mode == "dev":
        end = pd.Timestamp(d["dev_end"])
        ind, rf = ind.loc[:end], rf.loc[:end]
        first, last = pd.Timestamp(d["first_oos"]), end
    else:
        # The walk-forward runs continuously from the development start so that choices made on
        # PRIOR out-of-sample months (shrinkage alpha, band) have the same history as in
        # development; only months from final_start are scored.
        end = pd.Timestamp(d["final_end"])
        ind, rf = ind.loc[:end], rf.loc[:end]
        first, last = pd.Timestamp(d["first_oos"]), end
    Z, X, rff = french_design(ind, rf)
    if mode == "dev" and X.index.max() > pd.Timestamp(d["dev_end"]):
        raise ReservedSampleError("French data extend into the reserved final sample")
    score_from = None if mode == "dev" else pd.Timestamp(d["final_start"])
    return Z, X, rff, first, last, score_from


def extensions(W: dict, X: pd.DataFrame, rf: pd.Series, cfg: dict) -> dict:
    """Strategy paths (excess, turnover) including the predeclared extension family."""
    e, c = cfg["extension"], cfg["costs"]["base"]
    ew, aaf = W["EW"], W["AAF"]
    dates = aaf.index
    refit = cfg["forest"]["refit_months"]

    def score(ex, to):
        net = ex - c * to
        return net.mean() / net.std(ddof=1) if net.std() > 0 else -np.inf

    paths = {
        "EW": portfolio_path(ew, X, rf)[:2],
        "SR": portfolio_path(W["SR"], X, rf)[:2],
        "AAF": portfolio_path(aaf, X, rf)[:2],
    }
    mix = {
        a: (lambda a=a: portfolio_path(a * aaf + (1 - a) * ew, X, rf)[:2]) for a in e["alpha_grid"]
    }
    alpha = choose_on_past(mix, dates, refit, e["min_history_months"], e["default_alpha"], score)
    target = aaf.mul(alpha.astype(float), axis=0) + ew.mul(1 - alpha.astype(float), axis=0)
    paths["AAF_shrunk"] = portfolio_path(target, X, rf)[:2]
    bands = {b: (lambda b=b: portfolio_path(aaf, X, rf, band=b)[:2]) for b in e["band_grid"]}
    band = choose_on_past(bands, dates, refit, e["min_history_months"], e["default_band"], score)
    # Path-dependent band: simulate month by month with the band chosen for that month.
    held = _band_path(aaf, X, rf, band.astype(float))
    paths["AAF_band"] = held
    paths["AAF_quarterly"] = portfolio_path(aaf, X, rf, every=e["lowfreq_every"])[:2]
    paths["AAF_alpha0.5_fixed"] = portfolio_path(0.5 * aaf + 0.5 * ew, X, rf)[:2]
    return {"paths": paths, "alpha": alpha, "band": band}


def _band_path(target: pd.DataFrame, X, rf, band: pd.Series):
    dates = target.index
    R = X.loc[dates].to_numpy() + rf.loc[dates].to_numpy()[:, None]
    prev = np.zeros(target.shape[1])
    ex, to = [], []
    for i in range(len(dates)):
        tgt = target.iloc[i].to_numpy()
        w = tgt if i == 0 or np.abs(tgt - prev).sum() > band.iloc[i] else prev
        to.append(np.abs(w - prev).sum())
        ex.append(float(w @ X.loc[dates[i]].to_numpy()))
        prev = w * (1 + R[i]) / (1 + w @ R[i])
    return pd.Series(ex, index=dates), pd.Series(to, index=dates)


def run(
    root: Path,
    name: str,
    mode: str = "dev",
    seeds: list[int] | None = None,
    n_jobs: int = 4,
    leaf: str = "equality",
) -> dict:
    """``leaf``: ``equality`` (paper, w'Sigma w = sigma_EW^2) or ``relaxed`` (w'Sigma w <=
    sigma_EW^2), Generation 1b formulation comparison (configs/g1b_formulation.yaml)."""
    root = Path(root)
    tic = time.perf_counter()
    cfg = yaml.safe_load((root / "configs" / "study.yaml").read_text())
    if name == "archival_hw3" and mode != "dev":
        raise ValueError("the archival dataset has no reserved final sample")
    Z, X, rf, first, last, score_from = load_dataset(root, cfg, name, mode)
    fcfg = dict(cfg["forest"], mtry=cfg["datasets"][name]["mtry"], leaf=leaf)
    out = root / "results" / (f"{name}_{mode}" + ("" if leaf == "equality" else f"_{leaf}"))
    out.mkdir(parents=True, exist_ok=True)
    seeds = cfg["seeds"] if seeds is None else seeds
    rows, blocks, boots, diags, choices = [], [], {}, {}, {}
    for seed in seeds:
        wf = walk_forward(Z, X, rf, first, last, fcfg, seed, n_jobs)
        ext = extensions(wf["weights"], X, rf, cfg)
        diags[seed] = {
            "refits": wf["diagnostics"],
            "aaf_exante_vol_ratio": wf["aaf_exante_vol_ratio"].describe().to_dict(),
        }
        choices[seed] = {
            "alpha": ext["alpha"].astype(float).value_counts().to_dict(),
            "band": ext["band"].astype(float).value_counts().to_dict(),
        }
        for k, v in wf["weights"].items():
            v.to_parquet(out / f"weights_{k}_seed{seed}.parquet")
        paths = ext["paths"]
        if score_from is not None:
            paths = {k: (e.loc[score_from:], t.loc[score_from:]) for k, (e, t) in paths.items()}
        rfo = rf.loc[paths["EW"][0].index]
        for strat, (ex, to) in paths.items():
            be = break_even_cost(ex, to, *paths["EW"], rfo) if strat != "EW" else np.nan
            for c in cfg["costs"]["grid"]:
                m = metrics(ex, to, rfo, c)
                rows.append({"strategy": strat, "seed": seed, "cost": c, **m, "BE_bps_vs_EW": be})
            # Sequential evaluation blocks (net at base cost).
            net = ex - cfg["costs"]["base"] * to
            for b0 in range(0, len(net), cfg["blocks_months"]):
                seg = net.iloc[b0 : b0 + cfg["blocks_months"]]
                if len(seg) >= 24:
                    blocks.append(
                        {
                            "strategy": strat,
                            "seed": seed,
                            "start": str(seg.index[0].date()),
                            "end": str(seg.index[-1].date()),
                            "SR_net": float(seg.mean() / seg.std(ddof=1) * np.sqrt(12)),
                            "TO_pct": float(12 * to.iloc[b0 : b0 + len(seg)].mean() * 100),
                        }
                    )
        if seed == seeds[0]:
            base = cfg["costs"]["base"]
            net = {s: p[0] - base * p[1] for s, p in paths.items()}
            bb = cfg["bootstrap"]
            boots = {
                f"{s}_minus_EW": block_bootstrap_sr_diff(
                    net[s], net["EW"], bb["block_months"], bb["n_boot"]
                )
                for s in paths
                if s != "EW"
            }
            boots.update(
                {
                    f"{s}_minus_AAF": block_bootstrap_sr_diff(
                        net[s], net["AAF"], bb["block_months"], bb["n_boot"]
                    )
                    for s in ("AAF_shrunk", "AAF_band", "AAF_quarterly", "SR")
                }
            )
            pd.DataFrame({s: p[0] for s, p in paths.items()}).to_parquet(
                out / "excess_seed0.parquet"
            )
            pd.DataFrame({s: p[1] for s, p in paths.items()}).to_parquet(
                out / "turnover_seed0.parquet"
            )
    table = pd.DataFrame(rows)
    table.to_csv(out / "summary.csv", index=False)
    pd.DataFrame(blocks).to_csv(out / "blocks.csv", index=False)
    (out / "bootstrap_seed0.json").write_text(json.dumps(boots, indent=1))
    (out / "diagnostics.json").write_text(json.dumps(diags, indent=1, default=str))
    (out / "extension_choices.json").write_text(json.dumps(choices, indent=1, default=str))
    record = {
        "study": "asset-allocation-forests",
        "dataset": name,
        "mode": mode,
        "status": (
            "final evaluation (reserved sample)"
            if mode == "final"
            else cfg["datasets"][name].get("status", "development")
        ),
        "evaluation": {
            "first": str((score_from or first).date()),
            "last": str(min(last, X.index.max()).date()),
            "months": int(((X.index >= (score_from or first)) & (X.index <= last)).sum()),
            "walk_forward_start": str(first.date()),
        },
        "data": (
            {
                "path": cfg["datasets"][name].get("path"),
                "sha256": sha256_file(root / cfg["datasets"][name]["path"]),
            }
            if name == "archival_hw3"
            else json.loads((root / "data" / "french_manifest.json").read_text())
        ),
        "config_sha256": sha256_file(root / "configs" / "study.yaml"),
        "seeds": seeds,
        "source_tree_sha256": tree_hash(root),
        "git_commit": git_commit(root),
        "runtime_seconds": time.perf_counter() - tic,
        "environment": environment(PACKAGES),
        "leaf_formulation": leaf,
        "command": f"python scripts/run_study.py --dataset {name} --mode {mode} --leaf {leaf}",
    }
    outs = [
        out / f
        for f in (
            "summary.csv",
            "blocks.csv",
            "bootstrap_seed0.json",
            "diagnostics.json",
            "extension_choices.json",
        )
    ]
    write_manifest(out / "manifest.json", record, outs)
    return record


def rf_zero(e: pd.Series) -> pd.Series:
    return pd.Series(0.0, index=e.index)


def compare_formulations(root: Path, name: str, mode: str = "dev") -> dict:
    """Equality versus relaxed leaf formulation on identical months (seed 0 paths): gross and
    net Sharpe, realized volatility, turnover, concentration, and a paired block bootstrap of
    the net Sharpe difference (relaxed minus equality). Reads both runs' artifacts."""
    root = Path(root)
    cfg = yaml.safe_load((root / "configs" / "study.yaml").read_text())
    base = cfg["costs"]["base"]
    d_eq = root / "results" / f"{name}_{mode}"
    d_rx = root / "results" / f"{name}_{mode}_relaxed"
    ex = {k: pd.read_parquet(d / "excess_seed0.parquet") for k, d in (("eq", d_eq), ("rx", d_rx))}
    to = {k: pd.read_parquet(d / "turnover_seed0.parquet") for k, d in (("eq", d_eq), ("rx", d_rx))}
    if not ex["eq"].index.equals(ex["rx"].index):
        raise ValueError("formulation runs cover different months")
    out = {
        "months": int(len(ex["eq"])),
        "first": str(ex["eq"].index[0].date()),
        "last": str(ex["eq"].index[-1].date()),
        "base_cost": base,
        "strategies": {},
    }
    rec_eq = json.loads((d_eq / "manifest.json").read_text())
    if rec_eq.get("seeds", [0])[0] != 0:
        raise ValueError("formulation comparison expects seed 0 artifacts (excess_seed0)")
    for strat in ("AAF", "SR", "AAF_shrunk", "AAF_quarterly"):
        rec = {}
        for k in ("eq", "rx"):
            e, t = ex[k][strat], to[k][strat]
            net = e - base * t
            m = metrics(e, t, rf_zero(e), base)  # same turnover convention as the main tables
            rec[k] = {
                "SR_gross": float(e.mean() / e.std(ddof=1) * np.sqrt(12)),
                "SR_net": float(net.mean() / net.std(ddof=1) * np.sqrt(12)),
                "vol_ann_pct": float(e.std(ddof=1) * np.sqrt(12) * 100),
                "mean_ann_pct": float(e.mean() * 12 * 100),
                "TO_ann_pct": m["TO_pct"],
            }
        bb = cfg["bootstrap"]
        a = ex["rx"][strat] - base * to["rx"][strat]
        b = ex["eq"][strat] - base * to["eq"][strat]
        if np.allclose(a.to_numpy(), b.to_numpy(), rtol=0, atol=1e-15):
            rec["rx_minus_eq_net_SR"] = "n/a: identical under both formulations"
        else:
            rec["rx_minus_eq_net_SR"] = block_bootstrap_sr_diff(
                a, b, bb["block_months"], bb["n_boot"]
            )
        out["strategies"][strat] = rec
    scored = ex["eq"].index
    for k, d in (("eq", d_eq), ("rx", d_rx)):
        w = pd.read_parquet(d / "weights_AAF_seed0.parquet").loc[scored]  # scored months only
        out[f"{k}_mean_hhi"] = float((w**2).sum(axis=1).mean())
        out[f"{k}_mean_max_weight"] = float(w.max(axis=1).mean())
        diag = json.loads((d / "diagnostics.json").read_text())["0"]["refits"]
        first_refit = scored[0] - pd.DateOffset(months=cfg["forest"]["refit_months"])
        diag = [r for r in diag if pd.Timestamp(r["refit"]) > first_refit]  # refits in use
        out[f"{k}_slack_share_of_leaf_solves"] = float(
            sum(r.get("slack_leaf_solves", 0) for r in diag) / sum(r["leaf_solves"] for r in diag)
        )
    (root / "results" / f"{name}_{mode}_formulations.json").write_text(json.dumps(out, indent=1))
    return out
