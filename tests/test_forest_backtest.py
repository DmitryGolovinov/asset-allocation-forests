import numpy as np
import pandas as pd
import pytest

from aaf.backtest import break_even_cost, choose_on_past, metrics, portfolio_path, walk_forward
from aaf.data import parse_french_monthly
from aaf.forest import TreeBuilder, _moments_from_sums, predict_tree
from aaf.leaf import FastLeafSolver


def _data(T=240, N=5, J=4, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1990-01-31", periods=T, freq="ME")
    Z = pd.DataFrame(rng.normal(size=(T, J)), index=idx, columns=[f"z{j}" for j in range(J)])
    regime = (Z["z0"] > 0).to_numpy()
    mu = np.where(regime[:, None], [0.01, 0.0, 0.002, 0.004, 0.0], [0.0, 0.008, 0.002, 0.0, 0.004])
    X = pd.DataFrame(
        mu + rng.normal(0, 0.03, size=(T, N)), index=idx, columns=[f"a{i}" for i in range(N)]
    )
    rf = pd.Series(0.002, index=idx)
    return Z, X, rf


def test_moments_from_cumulative_sums_match_numpy():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(50, 5))
    mu, cov = _moments_from_sums(X.sum(0), X.T @ X, 50)
    assert np.allclose(mu, X.mean(0)) and np.allclose(cov, np.cov(X, rowvar=False))


def test_tree_respects_min_leaf_and_improvement_rule():
    Z, X, _ = _data()
    b = TreeBuilder(FastLeafSolver(5), max_depth=3, min_leaf=36, mtry=4)
    root = b.build(Z.to_numpy(), X.to_numpy(), np.random.default_rng(0))

    def check(node):
        assert node.n >= 36
        if not node.is_leaf:
            assert node.left.sr >= node.sr - 1e-12 and node.right.sr >= node.sr - 1e-12
            check(node.left)
            check(node.right)

    check(root)
    assert not root.is_leaf  # the planted regime should be found
    w = predict_tree(root, Z.to_numpy()[0])
    assert w.min() >= 0 and abs(w.sum() - 1) < 1e-12


def test_walk_forward_weights_do_not_use_future_returns():
    Z, X, rf = _data(T=200)
    cfg = {"n_trees": 8, "max_depth": 2, "min_leaf": 30, "mtry": 2, "refit_months": 12}
    first, last = X.index[120], X.index[-1]
    a = walk_forward(Z, X, rf, first, last, cfg, seed=0, n_jobs=1)
    X2 = X.copy()
    X2.iloc[150:] *= -2  # mutate outcomes after month 150
    b = walk_forward(Z, X2, rf, first, last, cfg, seed=0, n_jobs=1)
    # Weights up to the first refit that could see month 150 (month 156) must be identical.
    cut = X.index[156]
    pd.testing.assert_frame_equal(
        a["weights"]["AAF"].loc[:cut].iloc[:-1], b["weights"]["AAF"].loc[:cut].iloc[:-1]
    )


def test_portfolio_path_turnover_with_drift_by_hand():
    idx = pd.date_range("2000-01-31", periods=2, freq="ME")
    X = pd.DataFrame({"a": [0.10, 0.0], "b": [0.0, 0.0]}, index=idx)
    rf = pd.Series(0.0, index=idx)
    tgt = pd.DataFrame(0.5, index=idx, columns=["a", "b"])
    ex, to, _ = portfolio_path(tgt, X, rf)
    assert to.iloc[0] == pytest.approx(1.0)  # initial purchase from cash
    drift = np.array([0.55, 0.5]) / 1.05
    assert to.iloc[1] == pytest.approx(np.abs(0.5 - drift).sum())
    assert ex.iloc[0] == pytest.approx(0.05)


def test_band_and_low_frequency_controls_trade_less():
    Z, X, rf = _data(T=60, seed=2)
    rng = np.random.default_rng(0)
    tgt = pd.DataFrame(rng.dirichlet(np.ones(5), 60), index=X.index, columns=X.columns)
    _, to0, _ = portfolio_path(tgt, X, rf)
    _, to_inf, _ = portfolio_path(tgt, X, rf, band=10.0)
    _, to_q, _ = portfolio_path(tgt, X, rf, every=3)
    assert to_inf.iloc[1:].sum() == 0.0
    assert (to_q.iloc[1:][np.arange(1, 60) % 3 != 0] == 0).all()
    assert to_q.sum() < to0.sum()


def test_net_returns_follow_subtractive_convention_and_cost_monotonicity():
    idx = pd.date_range("2000-01-31", periods=24, freq="ME")
    rng = np.random.default_rng(3)
    ex = pd.Series(rng.normal(0.005, 0.02, 24), index=idx)
    to = pd.Series(0.3, index=idx)
    rf = pd.Series(0.001, index=idx)
    m0, m1 = metrics(ex, to, rf, 0.0), metrics(ex, to, rf, 0.01)
    assert m1["CW_net"] < m0["CW_net"]
    assert m0["CW_net"] == pytest.approx(m0["CW_gross"])


def test_choice_uses_prior_months_only():
    idx = pd.date_range("2000-01-31", periods=96, freq="ME")
    rng = np.random.default_rng(4)
    base = {k: pd.Series(rng.normal(0.001 * k, 0.02, 96), index=idx) for k in range(3)}
    zero = pd.Series(0.0, index=idx)

    def score(ex, to):
        return ex.mean()

    c1 = choose_on_past({k: (lambda k=k: (base[k], zero)) for k in base}, idx, 12, 36, 0, score)
    mutated = {k: v.copy() for k, v in base.items()}
    mutated[0].iloc[60:] += 1.0  # the future of candidate 0 becomes spectacular
    c2 = choose_on_past({k: (lambda k=k: (mutated[k], zero)) for k in base}, idx, 12, 36, 0, score)
    assert (c1.iloc[:61] == c2.iloc[:61]).all()
    assert (c1.iloc[:36] == 0).all()  # default before the minimum history


def test_break_even_cost_is_nan_when_behind_and_finite_when_ahead():
    idx = pd.date_range("2000-01-31", periods=60, freq="ME")
    rf = pd.Series(0.0, index=idx)
    ref = pd.Series(0.004, index=idx)
    ahead = pd.Series(0.006, index=idx)
    to_ref, to_a = pd.Series(0.02, index=idx), pd.Series(0.2, index=idx)
    be = break_even_cost(ahead, to_a, ref, to_ref, rf)
    # Monthly gap 0.002 closes when c * (0.2 - 0.02) = 0.002 -> c ~ 111 bps (compounding aside).
    assert 100 < be < 125
    assert np.isnan(break_even_cost(ref, to_a, ahead, to_ref, rf))


def test_french_parser_handles_percent_and_sentinels():
    text = (
        "Header text\n\n  Average Value Weighted Returns -- Monthly\n"
        ",A,B\n192607,  1.50, -99.99\n192608, -0.25,  2.00\n\n"
        "  Average Equal Weighted Returns -- Monthly\n,A,B\n192607, 9.0, 9.0\n"
    )
    df = parse_french_monthly(text, "Average Value Weighted Returns -- Monthly")
    assert df.shape == (2, 2)
    assert np.isnan(df.iloc[0, 1]) and df.iloc[1, 0] == -0.25
    assert df.index[0] == pd.Timestamp("1926-07-31")
