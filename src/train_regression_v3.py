"""v3 registry engine: the audited v2 logic (src/train_regression.py) with two changes only.

1. Grouped stratified CV: StratifiedGroupKFold for the outer folds (one shuffled split per repeat, seed split_seed +
   repeat) and for the inner alpha selection, stratified on severity class, groups = near-duplicate recordings.
2. Missing values: SimpleImputer(median) fitted inside every training fold, before StandardScaler.

Unchanged: StandardScaler -> Ridge with the alpha grid chosen by inner CV (same one-SVD-per-fold path as v2),
pooled out-of-fold Spearman averaged over repeats, joint (target, class) permutation with regenerated splits,
fold-matched DummyRegressor, bootstrap CI and Holm from stats_utils. Label-agnostic: functions take arrays;
real-label orchestration is run_registry_v3.py, synthetic gates are registry_gates_v3.py.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats_utils import bootstrap_ci, perm_pvalue, pooled_oof_spearman, spearman  # noqa: E402

BANNED_PARTS = ("nihss", "severity", "subject", "epoch", "lesion", "paralysis", "age", "sex", "gender", "duration",
                "onset", "handed", "stroke", "mbi", "mrs")


# ---------------------------------------------------------------- splitting and fitting

def grouped_splits(strata, groups, n_splits, seed):
    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return list(cv.split(np.zeros(len(strata)), strata, groups))


def preprocessor():
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])


def fit_ridge(X, y, strata, groups, settings):
    """Alpha by grouped inner CV (impute + scale fitted on inner-train only), then refit on all training rows."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    alphas = np.asarray(settings["alphas"], float)
    if len(alphas) < 1 or (alphas <= 0).any() or not np.isfinite(alphas).all() or (np.diff(alphas) < 0).any():
        raise ValueError("Alphas must be finite, positive, ascending")
    scores = np.zeros(len(alphas))
    for train, valid in grouped_splits(strata, groups, settings["inner_splits"], settings["split_seed"]):
        prep = preprocessor()
        a = prep.fit_transform(X[train])
        b = prep.transform(X[valid])
        xmean, ymean = a.mean(axis=0), y[train].mean()
        u, singular, vt = np.linalg.svd(a - xmean, full_matrices=False)
        weights = singular[:, None] / (singular[:, None] ** 2 + alphas[None, :])
        coefficients = vt.T @ (weights * (u.T @ (y[train] - ymean))[:, None])
        predicted = (b - xmean) @ coefficients + ymean
        scores += ((predicted - y[valid, None]) ** 2).mean(axis=0)
    alpha = float(alphas[np.argmin(scores)])
    model = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                      ("ridge", Ridge(alpha=alpha, solver="svd"))])
    model.fit(X, y)
    return model, alpha


def validate_arrays(X, y, strata, groups, settings, kind):
    X, y, strata, groups = np.asarray(X, float), np.asarray(y, float), np.asarray(strata), np.asarray(groups)
    if X.ndim != 2 or y.shape != (len(X),) or strata.shape != y.shape or groups.shape != y.shape or X.shape[1] < 1:
        raise ValueError("Invalid model matrix, target, strata or group dimensions")
    if not np.isfinite(y).all() or np.isinf(X).any():
        raise ValueError("Nonfinite target or infinite features")
    if kind == "association" and not np.isfinite(X).all():
        raise ValueError("Association tests require complete features")
    if kind == "ridge" and np.isnan(X).all(axis=0).any():
        raise ValueError("A feature column is entirely missing")
    classes, counts = np.unique(strata, return_counts=True)
    if len(classes) != 2 or counts.min() < settings["outer_splits"]:
        raise ValueError("Need two classes with enough subjects for stratification")
    return X, y, strata, groups


def cross_validated_predictions(X, y, strata, groups, settings, *, details=True):
    X, y, strata, groups = validate_arrays(X, y, strata, groups, settings, "ridge")
    repeats, folds = settings["outer_repeats"], settings["outer_splits"]
    prediction = np.full((len(y), repeats), np.nan)
    dummy = np.full_like(prediction, np.nan)
    membership = np.full((len(y), repeats), -1, dtype=int)
    alphas = []
    for repeat in range(repeats):
        for fold, (train, valid) in enumerate(grouped_splits(strata, groups, folds, settings["split_seed"] + repeat)):
            model, alpha = fit_ridge(X[train], y[train], strata[train], groups[train], settings)
            prediction[valid, repeat] = model.predict(X[valid])
            membership[valid, repeat] = fold
            alphas.append({"repeat": repeat, "fold": fold, "alpha": alpha})
            if details:
                dummy[valid, repeat] = DummyRegressor(strategy="mean").fit(X[train], y[train]).predict(X[valid])
    rho = pooled_oof_spearman(y, prediction)
    return {"rho": rho, "predictions": prediction, "dummy": dummy, "target": y, "strata": strata,
            "folds": membership, "alphas": alphas}


def prediction_metrics(y, strata, output):
    records = []
    for r in range(output["predictions"].shape[1]):
        pred, base = output["predictions"][:, r], output["dummy"][:, r]
        row = {"repeat": r, "rho": spearman(y, pred), "rmse": float(np.sqrt(mean_squared_error(y, pred))),
               "mae": float(mean_absolute_error(y, pred)), "r2": float(r2_score(y, pred)),
               "auc": float(roc_auc_score(strata, pred)),
               "dummy_rmse": float(np.sqrt(mean_squared_error(y, base))),
               "dummy_mae": float(mean_absolute_error(y, base)), "dummy_r2": float(r2_score(y, base))}
        for key in ("rmse", "mae", "r2"):
            row[key + "_minus_dummy"] = row[key] - row["dummy_" + key]
        records.append(row)
    return records


# ---------------------------------------------------------------- inference

def observed_statistic(X, y, strata, groups, settings, kind, details=True):
    if kind == "ridge":
        output = cross_validated_predictions(X, y, strata, groups, settings, details=details)
        return output["rho"], output
    return spearman(y, X[:, 0]), None


def evaluate(X, y, strata, groups, settings, test_number, kind="ridge", alternative=None):
    """Observed statistic, joint-permutation p, bootstrap CI and (ridge) prediction metrics."""
    if kind not in ("ridge", "association"):
        raise ValueError("Invalid registered analysis kind")
    X, y, strata, groups = validate_arrays(X, y, strata, groups, settings, kind)
    if kind == "association" and X.shape[1] != 1:
        raise ValueError("Association tests take exactly one feature")
    alternative = alternative or ("greater" if kind == "ridge" else "two-sided")
    statistic, output = observed_statistic(X, y, strata, groups, settings, kind)
    if not np.isfinite(statistic):
        raise ValueError("Observed statistic is undefined")
    rng = np.random.default_rng(settings["permutation_seed_base"] + test_number)
    null = np.empty(settings["permutations"])
    for b in range(len(null)):
        perm = rng.permutation(len(y))   # joint (target, class) permutation; groups stay with the recordings
        null[b] = observed_statistic(X, y[perm], strata[perm], groups, settings, kind, details=False)[0]
    p = perm_pvalue(statistic, null, alternative)
    ci = bootstrap_ci(y, output["predictions"] if output else X[:, 0], n_resamples=settings["bootstrap_resamples"],
                      seed=settings["bootstrap_seed_base"] + test_number, confidence=settings["confidence"],
                      max_invalid_fraction=settings["bootstrap_max_invalid_fraction"])
    repeat_metrics = prediction_metrics(y, strata, output) if output else []
    summary = {"rho": statistic, "p_raw": p, "ci_low": ci["low"], "ci_high": ci["high"], "ci_available": ci["available"],
               "bootstrap_invalid": ci["invalid"], "n": len(y), "mild": int((strata == 0).sum()),
               "moderate": int((strata == 1).sum()), "alternative": alternative}
    if repeat_metrics:
        summary.update({k: float(np.mean([row[k] for row in repeat_metrics])) for k in repeat_metrics[0] if k not in ("repeat", "rho")})
    else:
        summary["auc"] = float(roc_auc_score(strata, X[:, 0]))
    return {"summary": summary, "null": null, "bootstrap": ci["values"], "output": output, "repeat_metrics": repeat_metrics}


def describe(X, y, strata, groups, settings, kind):
    """Descriptive estimate only (sensitivities): no permutation, no CI."""
    X, y, strata, groups = validate_arrays(X, y, strata, groups, settings, kind)
    statistic, output = observed_statistic(X, y, strata, groups, settings, kind)
    out = {"rho": statistic, "n": len(y), "mild": int((strata == 0).sum()), "moderate": int((strata == 1).sum())}
    if output:
        metrics = prediction_metrics(y, strata, output)
        out.update({k: float(np.mean([m[k] for m in metrics])) for k in ("auc", "rmse", "dummy_rmse", "mae", "dummy_mae")})
    else:
        out["auc"] = float(roc_auc_score(strata, X[:, 0]))
    return out


def partial_spearman(x, y, z):
    """Spearman correlation of x and y after removing the linear effect of rank(z) from both ranks."""
    from scipy.stats import rankdata
    rx, ry, rz = (rankdata(np.asarray(v, float)) for v in (x, y, z))
    design = np.column_stack([np.ones(len(rz)), rz])
    res = [r - design @ np.linalg.lstsq(design, r, rcond=None)[0] for r in (rx, ry)]
    denom = np.linalg.norm(res[0]) * np.linalg.norm(res[1])
    return float(res[0] @ res[1] / denom) if denom else float("nan")


# ---------------------------------------------------------------- data loading (whitelist only)

def feature_list(root, spec):
    """Explicit feature list checked against the table's sidecar; 'all_sidecar' / 'all_ic' expand the contract."""
    contract = json.loads((Path(root) / spec["sidecar"]).read_text(encoding="utf-8"))
    columns = contract["columns"]
    if columns[0] != "subject_id" or len(columns) != len(set(columns)):
        raise ValueError("Invalid feature sidecar schema")
    if list(pd.read_csv(Path(root) / spec["table"], nrows=0).columns) != columns:
        raise ValueError("CSV columns/order differ from sidecar")
    features = spec["features"]
    if features == "all_sidecar":
        features = columns[1:]
    elif features == "all_ic":
        features = [c for c in columns[1:] if c.endswith("_IC")]
    missing = [f for f in features if f not in columns]
    if missing or not features or len(features) != len(set(features)):
        raise ValueError(f"Feature list invalid or not in sidecar: {missing}")
    if any(any(p in c.lower() for p in BANNED_PARTS) for c in features):
        raise ValueError("Banned model feature column")
    return list(features)


def load_test(root, spec, cfg, subjects, *, shuffle_seed=None, derive=None):
    """X, y, strata, groups, ids for one analysis. Shuffling jointly permutes (target, class) before return."""
    root = Path(root)
    features = feature_list(root, spec)
    table = pd.read_csv(root / spec["table"], usecols=["subject_id", *features])
    if derive:
        table[derive["name"]] = table[derive["mean_of"]].mean(axis=1)
        table, features = table[["subject_id", derive["name"]]], [derive["name"]]
    lab = cfg["labels"]
    labels = pd.read_csv(root / lab["file"], usecols=lab["columns"])
    groups = pd.read_csv(root / cfg["groups"]["file"], usecols=["subject_id", cfg["groups"]["column"]])
    for frame in (table, labels, groups):
        if frame["subject_id"].isna().any() or not frame["subject_id"].is_unique:
            raise ValueError("Missing/duplicate subject identifiers")
    subjects = sorted(subjects)
    merged = (pd.DataFrame({"subject_id": subjects})
              .merge(table, on="subject_id", how="left", validate="one_to_one")
              .merge(labels, on="subject_id", how="left", validate="one_to_one")
              .merge(groups, on="subject_id", how="left", validate="one_to_one"))
    if merged[["nihss_raw", "severity_class", cfg["groups"]["column"]]].isna().any().any():
        raise ValueError("Missing label or group for a cohort subject")
    if not set(subjects) <= set(table["subject_id"]):
        raise ValueError("Cohort subject missing from the feature table")
    strata = merged["severity_class"].map({"mild": 0, "moderate": 1, "0": 0, "1": 1, 0: 0, 1: 1})
    if strata.isna().any():
        raise ValueError("Invalid severity class")
    X = merged[features].to_numpy(float)
    y, classes = merged["nihss_raw"].to_numpy(float), strata.to_numpy(int)
    if not np.isfinite(y).all() or ((y < 1) | (y > 11)).any() or not np.array_equal(classes, (y >= 5).astype(int)):
        raise ValueError("Inconsistent target/class encoding")
    group_codes = pd.factorize(merged[cfg["groups"]["column"]])[0]
    if shuffle_seed is not None:
        perm = np.random.default_rng(shuffle_seed).permutation(len(y))
        y, classes = y[perm], classes[perm]
    return X, y, classes, group_codes, merged["subject_id"].tolist(), features
