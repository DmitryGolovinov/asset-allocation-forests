"""Tables and figures for the AAF note, rebuilt from results/<dataset>_<mode>/ artifacts.

Rights boundary: the supplied five-asset workbook's redistribution terms are not established.
Its time-series views (wealth paths, weight paths) and the Table 1 analogue of its asset
statistics are therefore written to a local, never-published directory; the public reports keep
the aggregate performance statistics only. Runs whose per-month artifacts (parquet files, not
published) are absent are skipped with a message."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PRIVATE = ROOT / "private"  # local-only outputs derived from the rights-uncertain workbook
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]


def style(ax, title):
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(color="#e6e5e0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)


def main(run: str) -> None:
    res = ROOT / "results" / run
    need = ["excess_seed0.parquet", "turnover_seed0.parquet", "weights_AAF_seed0.parquet"]
    if not all((res / f).exists() for f in need):
        print(f"skip {run}: per-month artifacts are not present (rerun the study to create them)")
        return
    man = json.loads((res / "manifest.json").read_text())
    ev = man["evaluation"]
    summ = pd.read_csv(res / "summary.csv")
    ex = pd.read_parquet(res / "excess_seed0.parquet")
    to = pd.read_parquet(res / "turnover_seed0.parquet")
    boots = json.loads((res / "bootstrap_seed0.json").read_text())
    diag = json.loads((res / "diagnostics.json").read_text())
    archival = run.startswith("archival")
    fig_dir = (PRIVATE if archival else ROOT / "reports") / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Figure 3 analogue: cumulative net excess wealth (seed 0, 20 bps).
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    for i, name in enumerate(["EW", "SR", "AAF", "AAF_shrunk", "AAF_quarterly"]):
        w = (1 + ex[name] - 0.002 * to[name]).cumprod()
        ax.plot(w.index, w.values, lw=1.5, color=PALETTE[i], label=name)
    ax.set_ylabel("Growth of 1 in excess of the risk-free rate")
    style(
        ax,
        f"Net of 20 bps per unit turnover, {ev['first']} to {ev['last']} ({man['mode']}, seed 0)",
    )
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(fig_dir / f"wealth_{run}.png")
    plt.close(fig)

    # Figure 2 analogue: AAF weight evolution (seed 0), stacked areas with fixed hue order.
    W = pd.read_parquet(res / "weights_AAF_seed0.parquet").loc[ev["first"] : ev["last"]]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    ax.stackplot(
        W.index,
        W.T.values,
        labels=W.columns,
        colors=PALETTE[: W.shape[1]],
        edgecolor="white",
        linewidth=0.3,
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("Weight")
    style(ax, f"AAF weights (seed 0), {ev['first']} to {ev['last']}")
    ax.legend(
        frameon=False, fontsize=7, ncol=W.shape[1], loc="upper left", bbox_to_anchor=(0, -0.08)
    )
    fig.tight_layout()
    fig.savefig(fig_dir / f"weights_{run}.png")
    plt.close(fig)

    b = summ[summ["cost"] == 0.002]
    agg = b.groupby("strategy").agg(
        TO_pct=("TO_pct", "mean"),
        SD_pct=("SD_pct_gross", "mean"),
        CW=("CW_gross", "mean"),
        SR=("SR_gross", "mean"),
        SR_seed_sd=("SR_gross", "std"),
        MaxDD=("MaxDD_pct_gross", "mean"),
        CW_net=("CW_net", "mean"),
        SR_net=("SR_net", "mean"),
        BE_bps=("BE_bps_vs_EW", "mean"),
    )
    agg = agg.loc[
        [
            s
            for s in [
                "EW",
                "SR",
                "AAF",
                "AAF_shrunk",
                "AAF_alpha0.5_fixed",
                "AAF_band",
                "AAF_quarterly",
            ]
            if s in agg.index
        ]
    ]
    blocks = pd.read_csv(res / "blocks.csv")
    blk = blocks.groupby(["start", "strategy"])["SR_net"].mean().unstack()
    d0 = pd.DataFrame(diag["0"]["refits"])
    solver = {
        "refits": len(d0),
        "leaf solves (seed 0)": int(d0["leaf_solves"].sum()),
        "exact-path fallbacks": int(d0["leaf_fallbacks"].sum()),
        "max |global objective - multistart ref|": float(d0["global_ref_gap"].abs().max()),
        "max global feasibility residual": float(d0["global_feas_resid"].max()),
        "max (relaxed - equality) objective": float(d0["global_relaxed_gap"].max()),
        "min relaxed var / EW var": float(d0["global_relaxed_var_ratio"].min()),
        "max cond(train covariance)": float(d0["cond_train_cov"].max()),
        "mean forest fit seconds": float(d0["forest_seconds"].mean()),
    }
    risk = diag["0"]["aaf_exante_vol_ratio"]
    scored = ev["walk_forward_start"] != ev["first"]  # a final run: history months not scored
    evd_path = res / "evaluation_diagnostics.json"
    evd = json.loads(evd_path.read_text())["seeds"]["0"] if evd_path.exists() else None
    lines = [
        f"# Results: {run}",
        "",
        f"Generated from `results/{run}/` (config `{man['config_sha256'][:12]}`, source tree "
        f"`{man['source_tree_sha256'][:12]}`). {ev['months']} months, {ev['first']} to "
        f"{ev['last']}. Status: {man['status']}. Seeds: {man['seeds']}.",
        "",
        "## Table 5 analogue (means over seeds; costs 20 bps per unit turnover)",
        "",
        "TO: annualized turnover (%); SD: annualized SD of excess returns (%); CW: cumulative "
        "wealth incl. the risk-free rate; SR: annualized Sharpe of excess returns; BE: cost at "
        "which net wealth equals EW's net wealth on the same trade schedules (NaN = behind EW "
        "at zero cost, inf = no crossing).",
        "",
        agg.to_markdown(floatfmt=".3f"),
        "",
        "## Joint block bootstrap of net Sharpe differences (seed 0, 12-month blocks)",
        "",
        pd.DataFrame(boots).T[["diff", "ci_lo", "ci_hi", "p_le_0"]].to_markdown(floatfmt=".3f"),
        "",
        "## Sequential blocks (net Sharpe, mean over seeds)",
        "",
        blk.to_markdown(floatfmt=".2f"),
        "",
        "## Leaf-solver and ensemble diagnostics",
        "",
    ]
    if scored and evd is not None:
        e, used = evd["exante_vol_ratio_scored_months"], evd["refits_used_for_scored_months"]
        lines += [
            f"Scored months only, seed 0 ({ev['months']} months; the {len(used)} refits whose "
            "forests set "
            f"their weights, {used[0]} to {used[-1]}; "
            "`scripts/evaluation_diagnostics.py`): leaf solves "
            f"{evd['leaf_solves']:,}, exact-path fallbacks {evd['exact_path_fallbacks']:,}, max "
            f"global feasibility residual {evd['max_global_feasibility_residual']:.1e}. Ex-ante "
            "volatility of the averaged forest portfolio relative to the EW target, using each "
            f"refit's training covariance: mean {e['mean']:.3f}, min {e['min']:.3f}, max "
            f"{e['max']:.3f}.",
            "",
            f"Whole walk-forward since {ev['walk_forward_start']} ({risk['count']:.0f} months, "
            f"{len(d0)} refits, including the development months that precede the scored "
            "period):",
            "",
        ]
    lines += [
        pd.Series(solver).to_frame("value").to_markdown(floatfmt=".3g"),
        "",
        ("Whole walk-forward: e" if scored else "E")
        + "x-ante volatility of the averaged forest portfolio relative to the EW target, using "
        f"each refit's training covariance: mean {risk['mean']:.3f}, min {risk['min']:.3f}, max "
        f"{risk['max']:.3f}. Averaging leaf portfolios that each satisfy the equality lands "
        "inside the volatility ball, not on it.",
        "",
    ]
    lines += (
        [
            "Wealth and weight paths of the archival run are not published: the supplied "
            "workbook's redistribution terms are not established."
        ]
        if archival
        else [f"![wealth](figures/wealth_{run}.png)", f"![weights](figures/weights_{run}.png)"]
    )
    (ROOT / "reports" / f"results_{run}.md").write_text("\n".join(lines) + "\n")
    print("wrote", run)


def formulations(name_mode: str) -> None:
    """Equality versus relaxed leaf (Generation 1b) from results/<name_mode>_formulations.json."""
    f = ROOT / "results" / f"{name_mode}_formulations.json"
    if not f.exists():
        return
    d = json.loads(f.read_text())
    rows = []
    for strat, rec in d["strategies"].items():
        for k, lab in (("eq", "equality (paper)"), ("rx", "relaxed (convex)")):
            rows.append({"strategy": strat, "leaf": lab, **rec[k]})
    t = pd.DataFrame(rows).set_index(["strategy", "leaf"])
    boot = {
        s: (
            r["rx_minus_eq_net_SR"]
            if isinstance(r["rx_minus_eq_net_SR"], str)
            else f"{r['rx_minus_eq_net_SR']['diff']:+.3f} "
            f"[{r['rx_minus_eq_net_SR']['ci_lo']:+.3f}, {r['rx_minus_eq_net_SR']['ci_hi']:+.3f}]"
        )
        for s, r in d["strategies"].items()
    }
    lines = [
        f"# Leaf formulation: equality versus convex inequality ({name_mode})",
        "",
        f"{d['months']} months, {d['first']} to {d['last']}, seed 0, base cost "
        f"{d['base_cost']} per unit turnover. Generated from `results/"
        f"{name_mode}_formulations.json`.",
        "",
        t.to_markdown(floatfmt=".3f"),
        "",
        "Net Sharpe difference, relaxed minus equality (paired 12-month block bootstrap, 95%):",
        "",
        "\n".join(f"- {s}: {v}" for s, v in boot.items()),
        "",
        f"Share of leaf solves where the relaxed risk constraint is slack: "
        f"{100 * d['rx_slack_share_of_leaf_solves']:.1f}%. Mean largest weight: equality "
        f"{d['eq_mean_max_weight']:.3f}, relaxed {d['rx_mean_max_weight']:.3f}; mean HHI "
        f"{d['eq_mean_hhi']:.3f} vs {d['rx_mean_hhi']:.3f}.",
    ]
    (ROOT / "reports" / f"formulations_{name_mode}.md").write_text("\n".join(lines) + "\n")
    print("wrote formulations", name_mode)


def table1() -> None:
    """Paper Table 1 analogue on the archival workbook (full sample and the two halves)."""
    from aaf.data import HW3_ASSETS, load_hw3

    df = load_hw3(ROOT / "data" / "HW3_dataset.xlsx")
    rows = []
    for label, sl in (
        ("1983-08..2023-01", slice(None)),
        ("1983-08..2003-07", slice(None, "2003-07-31")),
        ("2003-08..2023-01", slice("2003-08-31", None)),
    ):
        d = df.loc[sl]
        for a in HW3_ASSETS:
            r, rf = d[a], d["RF"]
            rows.append(
                {
                    "period": label,
                    "asset": a,
                    "AR_pct": 1200 * r.mean(),
                    "SD_pct": 100 * np.sqrt(12) * r.std(),
                    "SR": 12 * (r - rf).mean() / (np.sqrt(12) * r.std()),
                }
            )
    t = pd.DataFrame(rows).set_index(["period", "asset"])
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "table1_archival.md").write_text(
        "# Table 1 analogue (archival workbook)\n\nSR uses the SD of total returns, as in the "
        "paper's Table 1.\n\n" + t.to_markdown(floatfmt=".4f") + "\n"
    )


def paired_gap() -> None:
    """Relaxed-minus-equality optimal VALUE on the same stored node problems (development)."""
    res = ROOT / "results"
    sj = res / "paired_value_gap_summary.json"
    if not sj.exists():
        return
    s = json.loads(sj.read_text())
    full, by_fit = res / "paired_value_gap.csv", res / "paired_value_gap_by_fit.csv"
    if full.exists():  # 55 MB, regenerable (scripts/paired_value_gap.py); not published
        t = pd.read_csv(full)
        rows = []
        for (o, f), g in t.groupby(["origin", "grown_with"]):
            gap = 1e4 * g.loc[g["strict_gap"], "gap"]
            rows.append(
                {
                    "origin": o,
                    "grown_with": f,
                    "problems": len(g),
                    "strict_gap_share": g["strict_gap"].mean(),
                    "slack_status_share": g["slack_status"].mean(),
                    "slack_without_gap": int((g["slack_status"] & ~g["strict_gap"]).sum()),
                    "slack_without_gap_tied": int(
                        (g["slack_status"] & ~g["strict_gap"] & (g["n_best_mean_assets"] > 1)).sum()
                    ),
                    "gap_without_slack": int((~g["slack_status"] & g["strict_gap"]).sum()),
                    "tied_best_mean": int((g["n_best_mean_assets"] > 1).sum()),
                    "slack_tied": int((g["slack_status"] & (g["n_best_mean_assets"] > 1)).sum()),
                    "slack_tied_match": int(
                        (
                            g["slack_status"]
                            & (g["n_best_mean_assets"] > 1)
                            & (g["gap_condition_v_gt_b"] == g["strict_gap"])
                        ).sum()
                    ),
                    "unresolved": int(g["unresolved"].sum()) if "unresolved" in g else None,
                    "gap_bps_p50": gap.median(),
                    "gap_bps_p90": gap.quantile(0.9),
                    "gap_bps_max": gap.max(),
                }
            )
        pd.DataFrame(rows).to_csv(by_fit, index=False)
    tab = pd.read_csv(by_fit)
    a = s["by"]["all"]
    fits = pd.DataFrame(s["fits"])
    swg_tied = int(tab["slack_without_gap_tied"].sum()) if "slack_without_gap_tied" in tab else None
    swg_text = (
        "all with several assets tied for the best mean"
        if swg_tied == a["slack_without_gap"]
        else f"{swg_tied} of them with several assets tied for the best mean"
        if swg_tied is not None
        else "see the table"
    )
    lines = [
        "# Does the convex relaxation change the optimal value? Paired node problems",
        "",
        "Generated by `scripts/paired_value_gap.py` (per-problem table regenerable, not "
        "published) and `scripts/make_report.py`. Development data only; no final forest was "
        "refitted.",
        "",
        "Design (fixed before the run): the French five-industry forests refitted at the first "
        f"development refit on or after {', '.join(o[:7] for o in s['design']['origins'])}, "
        f"seed {s['design']['seed']}, {s['design']['trees_per_forest']} trees, each grown once "
        "with the paper's equality leaf and once with the relaxed leaf. Every (mean, covariance) "
        "passed to the leaf solver during growth was stored: node values and the children of "
        "every candidate split, not only terminal leaves. Both formulations were then solved "
        "exactly on EVERY stored problem, so each comparison is paired on one (mu, Sigma); the "
        "two forests of an origin split differently and meet different problems, which is why "
        "problems are not paired across forests.",
        "",
        f"**{a['problems']:,} problems.** The relaxed optimum is strictly higher in "
        f"{100 * a['strict_gap_share']:.1f}% of them (median gap "
        f"{a['median_gap_bps_per_month_given_gap']:.1f} bp of expected return per month when "
        f"there is one). The solver's slack status (a <= v) occurs without a value gap in "
        f"{a['slack_without_gap']} problems, {swg_text} "
        f"({a['tied_best_mean_problems']} tied problems in total); a gap without slack status "
        f"never occurs ({a['gap_without_slack']}). Largest equality feasibility residual: "
        f"{a['max_eq_feasibility_residual']:.1e}.",
        "",
    ]
    if "slack_problems" in a:
        n_tied, n_tied_match = int(tab["slack_tied"].sum()), int(tab["slack_tied_match"].sum())
        lines += [
            "**Checks that do not rely on the solver's own case analysis.** On a binding problem "
            "the relaxed solver returns the equality solution (proposition (ii)), so there the "
            "agreement of the condition v > b with the realized gap holds by construction and is "
            "not evidence. (1) On the "
            f"{a['slack_problems']:,} slack problems, where the relaxed value comes from the "
            "slack point and the equality value from face enumeration, the condition matched the "
            f"realized gap in {100 * a['condition_matches_gap_on_slack_resolved']:.2f}% of the "
            f"resolved ones. Of these, {a['slack_problems'] - n_tied:,} have a unique best asset "
            "with variance below v, where every feasible equality point has a lower mean, so the "
            f"match there follows from feasibility alone; the {n_tied} with tied best means are "
            f"the ones that test the equality enumeration ({n_tied_match} matched). "
            f"{a['unresolved_problems']} problems lie within the "
            f"{s['resolution']:.0e} resolution band (best and second-best means that close, or v "
            "that close to b) and are not classified, and there are "
            f"{a['condition_mismatches_resolved']} mismatches among all resolved problems. (2) An "
            "interior-point solve of the relaxation (Clarabel via cvxpy) on "
            f"{a['clarabel_binding_problems']:,} randomly drawn binding and "
            f"{a['clarabel_slack_problems']:,} slack problems: on binding problems its value "
            "exceeded the equality optimum by at most "
            f"{a['max_clarabel_minus_eq_on_binding']:.1e} (never), and its solutions lay "
            "slightly inside the risk constraint (relative variance shortfall: median "
            f"{-a['median_clarabel_rel_var_gap_on_binding']:.1e}, largest "
            f"{a['max_abs_clarabel_rel_var_gap_on_binding']:.1e} where the best two means differ "
            f"by {a['best_minus_second_mean_at_max_clarabel_var_gap']:.1e}, a "
            "nearly flat objective); it differed from the exact relaxed value by at most "
            f"{a['max_abs_clarabel_minus_exact_rx']:.1e}. (3) On the "
            f"{a['tied_best_mean_problems']} tied-mean problems the exact face minimum variance "
            "a (support enumeration) exceeded Clarabel's by at most "
            f"{a['max_rel_a_kkt_minus_clarabel_tied']:.1e} of v.",
            "",
        ]
    lines += [
        tab.to_markdown(index=False, floatfmt=".3f"),
        "",
        "Gap in basis points of monthly expected return, given a strict gap. Tolerances: "
        "v > b (1 + 1e-10) for the condition, gap > 1e-12 for a strict gap.",
        "",
        "Cost: "
        f"{fits['seconds'].sum():.0f} s to grow the six forests (single core) and "
        f"{s['evaluation_seconds']:.0f} s to solve both formulations on every stored problem.",
        "",
        "Why slack status is not the gap: with a unique best-mean asset, a = b and slack "
        "(a <= v) and a gap (v > b) differ only on the boundary v = b. With tied best means the "
        "face of best-mean assets has a < b, and v in [a, b] gives slack status with equal "
        "optimal values (both formulations reach the best mean). "
        "`tests/test_relaxed_theorem.py` contains one instance of each case.",
    ]
    (ROOT / "reports" / "paired_value_gap.md").write_text("\n".join(lines) + "\n")
    print("wrote paired_value_gap")


if __name__ == "__main__":
    for r in sys.argv[1:] or ["transfer_french5_dev", "transfer_french5_dev_relaxed"]:
        main(r)
        if not r.endswith("_relaxed"):
            formulations(r)
    if (ROOT / "data" / "HW3_dataset.xlsx").exists():  # private input; output stays private
        table1()
    paired_gap()
