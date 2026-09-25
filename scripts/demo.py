"""SYNTHETIC demonstration (no network): two regimes that favour different assets, detected by
one state variable. Runs the real forest, leaf solver and accounting; writes results/demo/."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aaf.backtest import metrics, portfolio_path, walk_forward  # noqa: E402

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    T = 300
    idx = pd.date_range("1990-01-31", periods=T, freq="ME")
    z = pd.DataFrame(rng.normal(size=(T, 3)), index=idx, columns=["state", "noise1", "noise2"])
    good = (z["state"].shift(1) > 0).to_numpy()  # regime known one month ahead via Z_{t-1}
    mu = np.where(good[:, None], [0.012, 0.0, 0.003, 0.004], [0.0, 0.009, 0.003, 0.002])
    X = pd.DataFrame(mu + rng.normal(0, 0.03, (T, 4)), index=idx, columns=list("ABCD"))
    rf = pd.Series(0.002, index=idx)
    Z = z.shift(1).bfill()  # the design convention: row t holds features known at t-1
    cfg = {"n_trees": 50, "max_depth": 2, "min_leaf": 36, "mtry": 2, "refit_months": 12}
    wf = walk_forward(Z, X, rf, idx[120], idx[-1], cfg, seed=0, n_jobs=1)
    rows = []
    for name, W in wf["weights"].items():
        ex, to, _ = portfolio_path(W, X, rf)
        rows.append({"strategy": name, **metrics(ex, to, rf.loc[ex.index], 0.002)})
    out = ROOT / "results" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "summary.csv", index=False)
    (out / "README.txt").write_text("SYNTHETIC demo output; not market evidence.\n")
    print(df[["strategy", "SR_net", "TO_pct"]].round(3).to_string(index=False))
