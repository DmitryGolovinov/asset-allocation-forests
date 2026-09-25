"""Expanding-window AAF backtest, accounting, and the shrinkage / trading-control extension.

Timing: the weights applied to month t come from features Z_{t-1} (row t of the design) and
a model fitted on rows strictly before the refit month. Returns are EXCESS returns X_t; total
returns X_t + rf_t drive the drift of weights between rebalances.

Turnover entering month t: ``TO_t = sum_i |w_t,i - w_{t-1,i}^+|`` with drifted weights
``w^+ = w (1 + R) / (1 + w'R)``; the first month buys from cash (TO = 1 for every strategy).
Net return (paper convention): ``r_net,t = r_t - c * TO_t``.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .forest import fit_forest, predict_forest
from .leaf import (
    ew_variance,
    solve_leaf_exact,
    solve_leaf_reference,
    solve_leaf_relaxed,
    solve_leaf_relaxed_exact,
)


def walk_forward(
    Z: pd.DataFrame,
    X: pd.DataFrame,
    rf: pd.Series,
    first_oos: pd.Timestamp,
    last_oos: pd.Timestamp,
    cfg: dict,
    seed: int,
    n_jobs: int = 4,
) -> dict:
    dates = X.index
    Zv, Xv = Z.to_numpy(), X.to_numpy()
    t0 = int(np.searchsorted(dates, first_oos))
    t1 = int(np.searchsorted(dates, last_oos, side="right"))
    N = X.shape[1]
    W = {k: np.zeros((t1 - t0, N)) for k in ("EW", "SR", "AAF")}
    diag, forest = [], None
    for t in range(t0, t1):
        if (t - t0) % cfg["refit_months"] == 0:
            tic = time.perf_counter()
            forest = fit_forest(Zv[:t], Xv[:t], cfg, seed=seed * 1000 + t, n_jobs=n_jobs)
            mu, Sig = Xv[:t].mean(axis=0), np.cov(Xv[:t], rowvar=False)
            glob = solve_leaf_exact(mu, Sig)
            ref = solve_leaf_reference(mu, Sig, starts=20, seed=t)
            rel = solve_leaf_relaxed(mu, Sig)
            # The unconditional Sharpe portfolio uses the same leaf formulation as the forest.
            relaxed = cfg.get("leaf", "equality") == "relaxed"
            g_used = solve_leaf_relaxed_exact(mu, Sig) if relaxed else glob
            w_sr = g_used.w
            diag.append(
                {
                    "refit": str(dates[t].date()),
                    "train_months": t,
                    "forest_seconds": time.perf_counter() - tic,
                    "leaf_solves": forest["leaf_solves"],
                    "leaf_fallbacks": forest["fallbacks"],
                    "leaf_formulation": cfg.get("leaf", "equality"),
                    "slack_leaf_solves": forest["slack_leaf_solves"],
                    "global_used_status": g_used.status,
                    "global_relaxed_exact_vs_cvxpy": (
                        solve_leaf_relaxed_exact(mu, Sig).objective - rel.objective
                    ),
                    "mean_depth": forest["mean_depth"],
                    "global_status": glob.status,
                    "global_feas_resid": glob.feasibility_residual,
                    "global_ref_gap": glob.objective - ref.objective,
                    "global_relaxed_gap": rel.objective - glob.objective,
                    "global_relaxed_var_ratio": float(rel.w @ Sig @ rel.w / ew_variance(Sig)),
                    "cond_train_cov": glob.cond,
                    "Sigma_train": Sig.tolist(),
                }
            )
        W["EW"][t - t0] = 1.0 / N
        W["SR"][t - t0] = w_sr
        W["AAF"][t - t0] = predict_forest(forest, Zv[t])
    oos = dates[t0:t1]
    # Ex-ante risk of the averaged forest portfolio relative to the EW target, using the
    # training covariance of the current refit (mixing breaks the equality constraint).
    risk_ratio = []
    for i, t in enumerate(range(t0, t1)):
        S = np.array(diag[(t - t0) // cfg["refit_months"]]["Sigma_train"])
        w = W["AAF"][i]
        risk_ratio.append(float(np.sqrt(w @ S @ w / ew_variance(S))))
    for d in diag:
        d.pop("Sigma_train")
    return {
        "dates": oos,
        "weights": {k: pd.DataFrame(v, index=oos, columns=X.columns) for k, v in W.items()},
        "diagnostics": diag,
        "aaf_exante_vol_ratio": pd.Series(risk_ratio, index=oos),
    }


def portfolio_path(
    target: pd.DataFrame, X: pd.DataFrame, rf: pd.Series, band: float = 0.0, every: int = 1
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Excess returns, turnover and held weights for a target-weight path.

    ``band``: trade to target only if ||target - drifted||_1 > band (no-trade band).
    ``every``: rebalance only every ``every`` months (lower-frequency control)."""
    dates = target.index
    Xv = X.loc[dates].to_numpy()
    R = Xv + rf.loc[dates].to_numpy()[:, None]
    held = np.zeros_like(target.to_numpy())
    to = np.zeros(len(dates))
    prev = np.zeros(target.shape[1])  # start in cash
    for i in range(len(dates)):
        tgt = target.iloc[i].to_numpy()
        if i == 0:
            w = tgt
        elif (i % every == 0) and np.abs(tgt - prev).sum() > band:
            w = tgt
        else:
            w = prev
        to[i] = np.abs(w - prev).sum()
        held[i] = w
        g = 1.0 + w @ R[i]
        prev = w * (1.0 + R[i]) / g
    ex = pd.Series((held * Xv).sum(axis=1), index=dates)
    return ex, pd.Series(to, index=dates), pd.DataFrame(held, index=dates, columns=target.columns)


def metrics(ex: pd.Series, to: pd.Series, rf: pd.Series, c: float) -> dict:
    """Paper-style metrics (annualized). SR uses the SD of excess returns."""
    net = ex - c * to
    out = {}
    for tag, r in (("gross", ex), ("net", net)):
        total = r + rf.loc[r.index]
        wealth = (1 + total).cumprod()
        out[f"SD_pct_{tag}"] = float(r.std(ddof=1) * np.sqrt(12) * 100)
        out[f"SR_{tag}"] = float(r.mean() / r.std(ddof=1) * np.sqrt(12))
        out[f"CW_{tag}"] = float(wealth.iloc[-1])
        out[f"MaxDD_pct_{tag}"] = float(-(wealth / wealth.cummax() - 1).min() * 100)
    T = len(to)
    out["TO_pct"] = float(12.0 / (T - 1) * to.iloc[1:].sum() * 100) if T > 1 else np.nan
    return out


def break_even_cost(
    ex: pd.Series, to: pd.Series, ex_ref: pd.Series, to_ref: pd.Series, rf: pd.Series
) -> float:
    """Proportional cost (bps per unit turnover) at which the strategy's net cumulative wealth
    equals the comparator's net wealth at the SAME cost (fixed trade schedules). NaN if the
    strategy is already behind at zero cost; inf if no crossing below 10,000 bps."""

    def gap(c):
        a = (1 + ex - c * to + rf.loc[ex.index]).prod()
        b = (1 + ex_ref - c * to_ref + rf.loc[ex.index]).prod()
        return a - b

    if gap(0.0) <= 0:
        return np.nan
    lo, hi = 0.0, 0.01
    while gap(hi) > 0:
        hi *= 2
        if hi > 1.0:
            return np.inf
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if gap(mid) > 0 else (lo, mid)
    return hi * 1e4


def choose_on_past(
    candidates: dict, dates: pd.DatetimeIndex, refit_every: int, min_hist: int, default, score
) -> pd.Series:
    """For each refit month pick the candidate with the best ``score`` on PRIOR months only.

    ``candidates`` maps a parameter to a function returning (excess, turnover) for all months;
    those paths must themselves be past-only for the choice to be honest (they are here:
    target weights at month t never use outcomes after t-1)."""
    paths = {k: f() for k, f in candidates.items()}
    choice = pd.Series(index=dates, dtype=object)
    for i in range(0, len(dates), refit_every):
        if i < min_hist:
            pick = default
        else:
            past = slice(0, i)
            pick = max(paths, key=lambda k: score(paths[k][0].iloc[past], paths[k][1].iloc[past]))
        choice.iloc[i : i + refit_every] = [pick] * len(choice.iloc[i : i + refit_every])
    return choice


def block_bootstrap_sr_diff(
    a: pd.Series, b: pd.Series, block: int = 12, n_boot: int = 2000, seed: int = 0
) -> dict:
    """Circular block bootstrap of SR(a) - SR(b) on the same resampled months.

    Resampling the same calendar blocks for both series (and hence for all assets) keeps
    cross-asset and cross-strategy dependence; it is unrelated to tree bagging or seeds."""
    rng = np.random.default_rng(seed)
    A, B = a.to_numpy(), b.to_numpy()
    T = len(A)

    def sr(x):
        return x.mean() / x.std(ddof=1) * np.sqrt(12)

    stats = np.empty(n_boot)
    nb = int(np.ceil(T / block))
    for i in range(n_boot):
        idx = ((rng.integers(0, T, nb)[:, None] + np.arange(block)) % T).ravel()[:T]
        stats[i] = sr(A[idx]) - sr(B[idx])
    lo, hi = np.quantile(stats, [0.025, 0.975])
    return {
        "diff": float(sr(A) - sr(B)),
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "p_le_0": float(np.mean(stats <= 0)),
        "block_months": block,
        "months": T,
    }
