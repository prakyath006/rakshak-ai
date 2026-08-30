"""Train, calibrate, and evaluate the chargeback risk model.

    python -m ml.train                 # full run
    python -m ml.train --sample 150000 # quick plumbing check (NOT a measurement)

WHAT THIS REPORTS AND WHY
-------------------------
The brief asks for "measured precision and recall on a held-out test set" and
"honest metrics including false-positive cost". So:

  * Precision and recall lead, at several operating points, because those are the
    words in the brief.
  * PR-AUC supports them. ROC-AUC is deliberately not the headline — at a 3.5%
    positive rate it reads around 0.9 for models that are not much use, because
    the vast negative class dominates the false-positive rate denominator.
  * Calibration is measured, not assumed. The cost policy multiplies rupees by a
    probability; if the probability is wrong the money is wrong.
  * Every model number is computed on the final time fold, which is touched once.

The calibrator is fitted on its own middle fold. Fitting it on test — or worse,
picking a threshold on test — would be scoring a decision on the data used to
make it.
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)

from ml.data import AMOUNT, LABEL, load_raw, time_split
from ml.features import build

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 192,
    "min_child_samples": 80,
    "feature_fraction": 0.7,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "max_bin": 255,
    "verbosity": -1,
    "seed": 42,
    # No scale_pos_weight: it distorts the predicted probabilities, and this
    # model exists to produce calibrated probabilities rather than a ranking.
}


@dataclass
class OperatingPoint:
    name: str
    threshold: float
    precision: float
    recall: float
    flagged: int
    flagged_rate: float
    true_positives: int
    false_positives: int


@dataclass
class Report:
    rows_train: int
    rows_calib: int
    rows_test: int
    fraud_rate_test: float
    pr_auc: float
    roc_auc: float
    brier_raw: float
    brier_calibrated: float
    calibration_bins: List[Dict[str, float]]
    operating_points: List[Dict[str, float]]
    top_features: List[Dict[str, float]]
    train_seconds: float


def _operating_point(
    name: str, y: np.ndarray, p: np.ndarray, threshold: float
) -> OperatingPoint:
    flagged = p >= threshold
    tp = int((flagged & (y == 1)).sum())
    fp = int((flagged & (y == 0)).sum())
    n_flagged = int(flagged.sum())
    precision = tp / n_flagged if n_flagged else 0.0
    recall = tp / int((y == 1).sum()) if (y == 1).any() else 0.0
    return OperatingPoint(
        name=name,
        threshold=float(threshold),
        precision=precision,
        recall=recall,
        flagged=n_flagged,
        flagged_rate=n_flagged / len(y),
        true_positives=tp,
        false_positives=fp,
    )


def _threshold_for_recall(y: np.ndarray, p: np.ndarray, target: float) -> float:
    precision, recall, thresholds = precision_recall_curve(y, p)
    # precision_recall_curve returns len(thresholds) == len(recall) - 1
    for r, t in zip(recall[:-1], thresholds):
        if r <= target:
            return float(t)
    return float(thresholds[0])


def _threshold_for_review_budget(p: np.ndarray, budget_rate: float) -> float:
    """Threshold that flags a fixed share of traffic.

    This is how a risk team actually sets a cut-off: an analyst team can review
    so many cases a day, not "whatever exceeds 0.5".
    """
    return float(np.quantile(p, 1.0 - budget_rate))


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> List[Dict[str, float]]:
    """Predicted vs. observed fraud rate by decile of predicted risk."""
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    idx = np.digitize(p, edges[1:-1], right=False)
    rows = []
    for b in range(bins):
        mask = idx == b
        if not mask.any():
            continue
        rows.append({
            "bin": b,
            "n": int(mask.sum()),
            "predicted": float(p[mask].mean()),
            "observed": float(y[mask].mean()),
        })
    return rows


def run(sample: Optional[int] = None, rounds: int = 1200) -> Report:
    print("Loading data ...")
    df = load_raw(nrows=sample)
    split = time_split(df)
    print(split.describe())

    print("\nBuilding features (encoders fitted on train only) ...")
    _encoder, (train, calib, test), features = build(split.train, split.calib, split.test)
    print(f"  {len(features)} model inputs")

    y_train = train[LABEL].to_numpy()
    y_calib = calib[LABEL].to_numpy()
    y_test = test[LABEL].to_numpy()

    print("\nTraining ...")
    started = time.time()
    booster = lgb.train(
        PARAMS,
        lgb.Dataset(train[features], label=y_train),
        num_boost_round=rounds,
        valid_sets=[lgb.Dataset(calib[features], label=y_calib)],
        callbacks=[lgb.early_stopping(80, verbose=False), lgb.log_evaluation(200)],
    )
    train_seconds = time.time() - started
    print(f"  {booster.best_iteration} trees in {train_seconds:.0f}s")

    raw_calib = booster.predict(calib[features], num_iteration=booster.best_iteration)
    raw_test = booster.predict(test[features], num_iteration=booster.best_iteration)

    # Calibrate on the middle fold; apply to the untouched test fold.
    print("Calibrating on the middle fold ...")
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(raw_calib, y_calib)
    p_test = iso.predict(raw_test)

    ops = [
        _operating_point("review budget 0.5% of traffic", y_test, p_test, _threshold_for_review_budget(p_test, 0.005)),
        _operating_point("review budget 1% of traffic", y_test, p_test, _threshold_for_review_budget(p_test, 0.01)),
        _operating_point("review budget 2% of traffic", y_test, p_test, _threshold_for_review_budget(p_test, 0.02)),
        _operating_point("recall 50%", y_test, p_test, _threshold_for_recall(y_test, p_test, 0.50)),
        _operating_point("recall 70%", y_test, p_test, _threshold_for_recall(y_test, p_test, 0.70)),
    ]

    gains = booster.feature_importance(importance_type="gain")
    order = np.argsort(gains)[::-1][:20]
    top = [{"feature": booster.feature_name()[i], "gain": float(gains[i])} for i in order]

    report = Report(
        rows_train=len(train),
        rows_calib=len(calib),
        rows_test=len(test),
        fraud_rate_test=float(y_test.mean()),
        pr_auc=float(average_precision_score(y_test, p_test)),
        roc_auc=float(roc_auc_score(y_test, p_test)),
        brier_raw=float(brier_score_loss(y_test, raw_test)),
        brier_calibrated=float(brier_score_loss(y_test, p_test)),
        calibration_bins=calibration_table(y_test, p_test),
        operating_points=[asdict(o) for o in ops],
        top_features=top,
        train_seconds=train_seconds,
    )

    ARTIFACT_DIR.mkdir(exist_ok=True)
    booster.save_model(str(ARTIFACT_DIR / "model.txt"), num_iteration=booster.best_iteration)

    # Both folds are saved. The calibration fold is what the money evaluation
    # tunes its baseline threshold on — tuning that on test would hand the
    # baseline an oracle and make the comparison meaningless.
    p_calib = iso.predict(raw_calib)
    for name, arr in (
        ("test_p", p_test), ("test_y", y_test), ("test_amount", test[AMOUNT].to_numpy()),
        ("calib_p", p_calib), ("calib_y", y_calib), ("calib_amount", calib[AMOUNT].to_numpy()),
    ):
        np.save(ARTIFACT_DIR / f"{name}.npy", arr)

    # The calibrator is part of the model: raw LightGBM scores are not
    # probabilities, and the money layer needs probabilities.
    with open(ARTIFACT_DIR / "calibrator.pkl", "wb") as fh:
        pickle.dump(iso, fh)

    (ARTIFACT_DIR / "report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

    return report


def print_report(r: Report) -> None:
    print("\n" + "=" * 74)
    print("HELD-OUT TEST FOLD — final 31 days, never seen in training or calibration")
    print("=" * 74)
    print(f"  rows {r.rows_test:,}   fraud rate {r.fraud_rate_test:.3%}")
    print()
    print(f"  PR-AUC (headline)      {r.pr_auc:.4f}      baseline = fraud rate = {r.fraud_rate_test:.4f}")
    print(f"  lift over baseline     {r.pr_auc / r.fraud_rate_test:.1f}x")
    print(f"  ROC-AUC (context only) {r.roc_auc:.4f}")
    print(f"  Brier  raw {r.brier_raw:.5f} -> calibrated {r.brier_calibrated:.5f}")

    print("\n  PRECISION AND RECALL AT REAL OPERATING POINTS")
    print(f"  {'operating point':<32}{'thresh':>9}{'prec':>8}{'recall':>8}{'flagged':>10}{'FP':>8}")
    for o in r.operating_points:
        print(
            f"  {o['name']:<32}{o['threshold']:>9.4f}{o['precision']:>8.1%}"
            f"{o['recall']:>8.1%}{o['flagged']:>10,}{o['false_positives']:>8,}"
        )

    print("\n  CALIBRATION — predicted vs observed, by decile of risk")
    print(f"  {'bin':<5}{'n':>9}{'predicted':>12}{'observed':>11}")
    for b in r.calibration_bins:
        print(f"  {b['bin']:<5}{b['n']:>9,}{b['predicted']:>12.4f}{b['observed']:>11.4f}")

    print("\n  TOP FEATURES BY GAIN")
    for f in r.top_features[:12]:
        print(f"    {f['feature']:<28}{f['gain']:>14,.0f}")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None, help="row prefix for a plumbing check")
    ap.add_argument("--rounds", type=int, default=1200)
    args = ap.parse_args()
    print_report(run(sample=args.sample, rounds=args.rounds))
