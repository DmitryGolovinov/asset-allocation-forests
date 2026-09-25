"""Regressions for defects found in an earlier internal technical review."""

import numpy as np
import pytest

from aaf.leaf import FastLeafSolver, solve_leaf_exact, solve_leaf_reference


def _zero_variance_case():
    # Asset 3 has zero variance inside the leaf and the highest mean. Sigma is singular but the
    # covariance restricted to the face's affine hull is positive definite.
    S = np.diag([0.0025, 0.0016, 0.0036, 0.0])
    S[0, 1] = S[1, 0] = 0.0008
    return np.array([0.006, 0.004, 0.007, 0.008]), S


def test_zero_variance_asset_face_is_not_skipped():
    # Before the fix: Cholesky of Sigma_S failed on every face containing asset 3, the solver
    # returned the equal-weight fallback (objective 0.00625) although 0.007598 is feasible.
    mu, S = _zero_variance_case()
    ex = solve_leaf_exact(mu, S)
    ref = solve_leaf_reference(mu, S, starts=40)
    assert ex.status == "ok" and ex.feasibility_residual < 1e-10
    assert ex.objective >= ref.objective - 1e-12
    assert ex.objective == pytest.approx(0.0075981812, abs=1e-9)


def test_fast_solver_routes_singular_leaves_to_exact_path():
    mu, S = _zero_variance_case()
    fs = FastLeafSolver(4)
    w, _ = fs.solve(mu, S)
    assert fs.fallbacks == 1
    assert mu @ w == pytest.approx(solve_leaf_exact(mu, S).objective, abs=1e-12)


def test_hull_coordinates_agree_with_previous_closed_form_on_pd_problems():
    rng = np.random.default_rng(3)
    for _ in range(20):
        A = rng.normal(size=(5, 5))
        S = A @ A.T / 50 + 1e-4 * np.eye(5)
        mu = rng.normal(0.004, 0.003, 5)
        ex = solve_leaf_exact(mu, S)
        ref = solve_leaf_reference(mu, S, starts=20)
        assert ex.objective >= ref.objective - 1e-10 and ex.feasibility_residual < 1e-9


def test_final_mode_walk_forward_keeps_development_history(tmp_path, monkeypatch):
    # The final French run must start its walk-forward at the development start (so prior-OOS
    # selections see the same history) and score only months from final_start.
    import pandas as pd
    import yaml

    from aaf import study

    cfg = yaml.safe_load(open("configs/study.yaml"))
    idx = pd.date_range("1926-07-31", "2026-07-31", freq="ME")
    ind = pd.DataFrame(0.01, index=idx, columns=list("ABCDE"))
    monkeypatch.setattr(study, "load_french", lambda _: (ind, pd.Series(0.001, index=idx)))
    *_, first, last, score_from = study.load_dataset(tmp_path, cfg, "transfer_french5", "final")
    d = cfg["datasets"]["transfer_french5"]
    assert first == pd.Timestamp(d["first_oos"]) and score_from == pd.Timestamp(d["final_start"])
    *_, first_dev, last_dev, sf_dev = study.load_dataset(tmp_path, cfg, "transfer_french5", "dev")
    assert sf_dev is None and last_dev == pd.Timestamp(d["dev_end"])
