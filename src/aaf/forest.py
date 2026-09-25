"""Asset Allocation Trees and Forest (Bettencourt, Petukhina & Tetereva, SSRN 4781685).

Tree rule as printed in the paper (Section 3.2):

* a node's value is SR*, the Sharpe ratio of the leaf problem (eq. 2, lambda = 0) solved on
  the node's observations (mean and covariance of excess returns);
* a split (j, c) sends Z_j < c left; it is admissible if both children have at least
  ``min_leaf`` observations and BOTH children's SR* are >= the parent's SR*;
* the chosen split maximizes eq. (3): SR*_left / n_left + SR*_right / n_right (the paper's
  normalization, reproduced as printed; it favors splits that isolate a small high-SR leaf);
* depth <= 3, min leaf 36, ``mtry`` candidate features drawn per split, 200 bootstrap trees;
  forest weights are the average of the trees' leaf weights (already on the simplex).

Deviation (documented): candidate thresholds are the node's empirical deciles (9 values)
rather than every observed value, for tractability of the walk-forward.
Node moments are computed from cumulative sums, so each candidate costs O(N^2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .leaf import FastLeafSolver


@dataclass
class Node:
    feature: int = -1
    threshold: float = np.nan
    left: Node | None = None
    right: Node | None = None
    w: np.ndarray | None = None
    sr: float = np.nan
    n: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.left is None


def _moments_from_sums(s1: np.ndarray, s2: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    mu = s1 / n
    cov = (s2 - n * np.outer(mu, mu)) / (n - 1)
    return mu, 0.5 * (cov + cov.T)


class TreeBuilder:
    def __init__(
        self,
        solver: FastLeafSolver,
        max_depth: int = 3,
        min_leaf: int = 36,
        mtry: int = 4,
        q_grid: np.ndarray | None = None,
    ):
        self.solver = solver
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.mtry = mtry
        self.q_grid = np.linspace(0.1, 0.9, 9) if q_grid is None else q_grid

    def leaf_value(self, X: np.ndarray) -> tuple[np.ndarray, float]:
        mu = X.mean(axis=0)
        cov = np.cov(X, rowvar=False)
        return self.solver.solve(mu, cov)

    def build(self, Z: np.ndarray, X: np.ndarray, rng: np.random.Generator) -> Node:
        return self._grow(Z, X, np.arange(len(X)), 0, rng)

    def _grow(self, Z, X, rows, depth, rng) -> Node:
        w, sr = self.leaf_value(X[rows])
        node = Node(w=w, sr=sr, n=len(rows))
        if depth >= self.max_depth or len(rows) < 2 * self.min_leaf:
            return node
        best = (-np.inf, None, None, None)
        feats = rng.choice(Z.shape[1], size=min(self.mtry, Z.shape[1]), replace=False)
        Xr = X[rows]
        tot1 = Xr.sum(axis=0)
        tot2 = Xr.T @ Xr
        n = len(rows)
        for j in feats:
            z = Z[rows, j]
            order = np.argsort(z, kind="mergesort")
            zs, Xs = z[order], Xr[order]
            c1 = np.cumsum(Xs, axis=0)
            c2 = np.cumsum(Xs[:, :, None] * Xs[:, None, :], axis=0)
            for c in np.unique(np.quantile(zs, self.q_grid)):
                nl = int(np.searchsorted(zs, c, side="left"))  # rows with z < c
                nr = n - nl
                if nl < self.min_leaf or nr < self.min_leaf:
                    continue
                mu_l, cov_l = _moments_from_sums(c1[nl - 1], c2[nl - 1], nl)
                mu_r, cov_r = _moments_from_sums(tot1 - c1[nl - 1], tot2 - c2[nl - 1], nr)
                _, sr_l = self.solver.solve(mu_l, cov_l)
                if sr_l < sr:
                    continue
                _, sr_r = self.solver.solve(mu_r, cov_r)
                if sr_r < sr:
                    continue
                obj = sr_l / nl + sr_r / nr  # paper eq. (3), as printed
                if obj > best[0]:
                    best = (obj, j, c, order[:nl])
        if best[1] is None:
            return node
        _, j, c, left_local = best
        mask = np.zeros(n, dtype=bool)
        mask[left_local] = True
        node.feature, node.threshold = int(j), float(c)
        node.left = self._grow(Z, X, rows[mask], depth + 1, rng)
        node.right = self._grow(Z, X, rows[~mask], depth + 1, rng)
        return node


def predict_tree(node: Node, z: np.ndarray) -> np.ndarray:
    while not node.is_leaf:
        node = node.left if z[node.feature] < node.threshold else node.right
    return node.w


def depth_of(node: Node) -> int:
    return 0 if node.is_leaf else 1 + max(depth_of(node.left), depth_of(node.right))


def _fit_one(Z, X, seed, cfg):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(X), len(X))  # bootstrap rows (bagging)
    solver = FastLeafSolver(X.shape[1], cfg.get("leaf", "equality"))
    tree = TreeBuilder(solver, cfg["max_depth"], cfg["min_leaf"], cfg["mtry"]).build(
        Z[idx], X[idx], rng
    )
    return tree, solver.calls, solver.fallbacks, solver.slack


def fit_forest(Z: np.ndarray, X: np.ndarray, cfg: dict, seed: int, n_jobs: int = 4) -> dict:
    """Fit ``cfg['n_trees']`` trees. Seeds are deterministic functions of ``seed``."""
    from joblib import Parallel, delayed

    seeds = [int(seed) * 100_003 + b for b in range(cfg["n_trees"])]
    res = Parallel(n_jobs=n_jobs)(delayed(_fit_one)(Z, X, s, cfg) for s in seeds)
    trees = [r[0] for r in res]
    return {
        "trees": trees,
        "leaf_solves": int(sum(r[1] for r in res)),
        "fallbacks": int(sum(r[2] for r in res)),
        "slack_leaf_solves": int(sum(r[3] for r in res)),
        "mean_depth": float(np.mean([depth_of(t) for t in trees])),
    }


def predict_forest(forest: dict, z: np.ndarray) -> np.ndarray:
    ws = np.array([predict_tree(t, z) for t in forest["trees"]])
    w = ws.mean(axis=0)
    return w / w.sum()
