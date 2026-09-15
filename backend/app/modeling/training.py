"""Two fixed classifiers, student-grouped evaluation and atomic local artifacts."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import joblib
import numpy as np
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.dashboard.data import Snapshot
from app.models import Course, ModelRun
from app.modeling.features import BADGE_LABELS, GRADE_LABELS, build_training_data, data_signature

MODEL_VERSION = "model-v1"
RANDOM_SEED = 20260914
MODEL_CONFIG = {
    "model_version": MODEL_VERSION, "folds": 3, "seed": RANDOM_SEED,
    "selection": "macro_f1_then_balanced_accuracy_tie_prefers_logistic",
    "logistic": {"C": 1.0, "class_weight": "balanced", "max_iter": 1000},
    "random_forest": {"trees": 300, "max_depth": 5, "min_samples_leaf": 5,
                      "class_weight": "balanced_subsample"},
    "badge_wait_days": 60,
}


def config_hash():
    return sha256(json.dumps(MODEL_CONFIG, sort_keys=True).encode()).hexdigest()


def estimators(features):
    numeric = ColumnTransformer([("numeric", Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("scale", StandardScaler()),
    ]), features)], remainder="drop")
    forest_inputs = ColumnTransformer([("numeric", SimpleImputer(
        strategy="median", add_indicator=True, keep_empty_features=True), features)], remainder="drop")
    return {
        "logistic_regression": Pipeline([("prepare", numeric), ("classifier", LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=1000, random_state=RANDOM_SEED))]),
        "random_forest": Pipeline([("prepare", forest_inputs), ("classifier", RandomForestClassifier(
            n_estimators=300, max_depth=5, min_samples_leaf=5, max_features="sqrt",
            class_weight="balanced_subsample", random_state=RANDOM_SEED, n_jobs=1))]),
    }


def grouped_splits(labels, groups, expected):
    y, group_values = np.asarray(labels), np.asarray(groups)
    for seed in range(RANDOM_SEED, RANDOM_SEED + 100):
        folds = list(StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=seed).split(
            np.zeros(len(y)), y, group_values))
        if all(set(y[train]) == set(expected) and set(y[test]) == set(expected) for train, test in folds):
            return folds, seed
    return None, None


def readiness(dataset, expected):
    counts = Counter(dataset.labels)
    if set(counts) != set(expected):
        return "missing_target_class", counts, None, None
    if min(counts.values()) < 3:
        return "class_has_fewer_than_three_students", counts, None, None
    if len(set(dataset.groups)) < 20:
        return "fewer_than_twenty_students", counts, None, None
    folds, seed = grouped_splits(dataset.labels, dataset.groups, expected)
    if folds is None:
        return "no_valid_three_fold_group_split", counts, None, None
    return None, counts, folds, seed


def evaluate(model, frame, labels, folds, expected):
    fold_metrics, matrix = [], np.zeros((len(expected), len(expected)), dtype=int)
    y = np.asarray(labels)
    for train, test in folds:
        fitted = clone(model).fit(frame.iloc[train], y[train])
        predicted = fitted.predict(frame.iloc[test])
        fold_metrics.append({
            "macro_f1": float(f1_score(y[test], predicted, labels=expected, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y[test], predicted)),
        })
        matrix += confusion_matrix(y[test], predicted, labels=expected)
    result = {key: float(np.mean([row[key] for row in fold_metrics])) for key in ("macro_f1", "balanced_accuracy")}
    result.update({key + "_std": float(np.std([row[key] for row in fold_metrics], ddof=1)) for key in result.copy()})
    result["folds"] = fold_metrics
    result["confusion_matrix"] = matrix.tolist()
    return result


def choose(results):
    logistic, forest = results["logistic_regression"], results["random_forest"]
    if forest["macro_f1"] > logistic["macro_f1"] + .01:
        return "random_forest"
    if abs(forest["macro_f1"] - logistic["macro_f1"]) <= .01:
        return "random_forest" if forest["balanced_accuracy"] > logistic["balanced_accuracy"] + .01 else "logistic_regression"
    return "logistic_regression"


def artifact_valid(run, settings):
    if not run.artifact_path or not run.artifact_sha256:
        return False
    path = (settings.model_artifact_root / run.artifact_path).resolve()
    root = settings.model_artifact_root.resolve()
    return path.parent == root and path.is_file() and sha256(path.read_bytes()).hexdigest() == run.artifact_sha256


def write_artifact(settings, filename, bundle):
    root = settings.model_artifact_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    path, temporary = root / filename, root / (filename + ".tmp")
    joblib.dump(bundle, temporary, compress=3)
    os.replace(temporary, path)
    return filename, sha256(path.read_bytes()).hexdigest()


def train(session, settings, course_code, target):
    course = session.scalar(select(Course).where(Course.code == course_code))
    if course is None:
        raise ValueError("unknown_course")
    if target not in {"AT1", "AT2", "weighted_final", "badge"}:
        raise ValueError("unknown_target")
    data = Snapshot(session)
    signature = data_signature(data, course.id, target, settings.badge_data_as_of, MODEL_CONFIG)
    current = session.scalar(select(ModelRun).where(ModelRun.course_id == course.id, ModelRun.target == target,
        ModelRun.status == "completed", ModelRun.data_sha256 == signature,
        ModelRun.config_sha256 == config_hash()).order_by(ModelRun.finished_at.desc(), ModelRun.id.desc()))
    if current and artifact_valid(current, settings):
        return current, True
    run = ModelRun(model_name="none", model_version=MODEL_VERSION, course_id=course.id, target=target,
        cohort_policy="student_grouped", status="running", config_sha256=config_hash(), data_sha256=signature)
    session.add(run); session.commit()
    try:
        if target == "badge" and settings.badge_data_as_of is None:
            reason, dataset = "badge_data_as_of_required", None
        else:
            dataset = build_training_data(data, course.id, target, settings.badge_data_as_of)
            expected = BADGE_LABELS if target == "badge" else GRADE_LABELS
            reason, counts, folds, split_seed = readiness(dataset, expected)
        if reason:
            run.status, run.finished_at = "insufficient", datetime.now(timezone.utc)
            run.summary = {"reason": reason, **(dataset.summary if dataset else {}),
                           "class_counts": dict(Counter(dataset.labels)) if dataset else {}}
            session.commit()
            return run, False
        candidates = estimators(dataset.feature_names)
        results = {name: evaluate(model, dataset.frame, dataset.labels, folds, expected)
                   for name, model in candidates.items()}
        selected = choose(results)
        fitted = candidates[selected].fit(dataset.frame, dataset.labels)
        bundle = {"pipeline": fitted, "feature_names": dataset.feature_names, "classes": list(expected),
                  "course": course_code, "target": target, "model_version": MODEL_VERSION,
                  "data_sha256": signature, "config_sha256": config_hash()}
        filename = f"{course_code}__{target}__{run.id}.joblib"
        run.artifact_path, run.artifact_sha256 = write_artifact(settings, filename, bundle)
        run.model_name, run.metrics = selected, results
        run.summary = {**dataset.summary, "class_counts": dict(counts), "split_seed": split_seed,
                       "badge_data_as_of": str(settings.badge_data_as_of) if target == "badge" else None,
                       "warnings": (["low_class_support"] if min(counts.values()) < 20 else []) +
                                   (["single_offering_training"] if dataset.summary["contributing_offerings"] < 2 else [])}
        run.status, run.finished_at = "completed", datetime.now(timezone.utc)
        session.commit()
        return run, False
    except Exception:
        session.rollback()
        failed = session.get(ModelRun, run.id)
        failed.status, failed.finished_at = "failed", datetime.now(timezone.utc)
        failed.summary = {"reason": "training_failed"}
        session.commit()
        raise


def load_model(session, settings, course_code, target):
    run = session.scalar(select(ModelRun).join(Course).where(Course.code == course_code,
        ModelRun.target == target, ModelRun.status == "completed").order_by(ModelRun.finished_at.desc(), ModelRun.id.desc()))
    if run is None or not artifact_valid(run, settings):
        return None
    return joblib.load(settings.model_artifact_root / run.artifact_path), run
