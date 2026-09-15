"""Rank associations with student-cluster bootstrap; no predictive model fitting."""
import numpy as np


def ranks(values):
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return (np.cumsum(counts) - (counts - 1) / 2)[inverse]


def correlation(x, y, strata=None):
    x, y = ranks(x).astype(float), ranks(y).astype(float)
    if strata is not None:
        # Remove each offering's mean rank: a within-offering rank association,
        # not a causal adjustment for every possible confounder.
        for group in np.unique(strata):
            ix = strata == group
            x[ix] -= x[ix].mean()
            y[ix] -= y[ix].mean()
    x, y = x - x.mean(), y - y.mean()
    denominator = np.sqrt((x @ x) * (y @ y))
    return float(x @ y / denominator) if denominator > 0 else None


def association(rows, feature, outcome):
    x = np.array([r[feature] for r in rows], dtype=float)
    y = np.array([r[outcome] for r in rows], dtype=float)
    strata = np.array([r['offering'] for r in rows])
    students = np.array([r['student'] for r in rows])
    raw = correlation(x, y)
    within = correlation(x, y, strata)
    result = {"spearman_rho": raw, "within_offering_rank_r": within,
              "rho_ci_low": None, "rho_ci_high": None}
    # Sparse/constant samples get no spurious interval. Clusters keep repeated
    # learning experiences of the same student together when resampling.
    unique = np.unique(students)
    if len(unique) < 20 or raw is None:
        return result
    clusters = [np.flatnonzero(students == s) for s in unique]
    rng = np.random.default_rng(20260914)
    estimates = []
    for _ in range(200):
        ix = np.concatenate([clusters[i] for i in rng.integers(0, len(clusters), len(clusters))])
        value = correlation(x[ix], y[ix])
        if value is not None:
            estimates.append(value)
    if len(estimates) >= 180:
        result['rho_ci_low'], result['rho_ci_high'] = map(float, np.quantile(estimates, [.025, .975]))
    return result
