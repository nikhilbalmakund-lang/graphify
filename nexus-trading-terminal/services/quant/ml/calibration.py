"""Calibrated probability model for "TP1 reached before the stop".

Machine learning is only used where the stored history supports it:

* Label: for FILLED historical setups, 1 if TP1 was reached before the stop.
* Features: the versioned similarity vector, direction, signal score, planned
  R:R, regime and asset class (one-hot).
* Split strictly by time: train 60% / calibration 20% / test 20%.
* Model: logistic regression (transparent baseline) with isotonic
  calibration fitted on the calibration split. A gradient-boosting
  challenger (scikit-learn HistGradientBoosting, LightGBM-style) is evaluated
  for comparison only.
* Gate: the model is CALIBRATED only if the untouched test split has
  n >= 100, expected calibration error <= 0.05 and a positive Brier skill
  score versus the base rate. Otherwise its outputs are NEVER displayed as
  probabilities.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, Field
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from quant.ml.memory import SetupRecord
from quant.regime.detector import REGIME_CODES

MODEL_NAME = "setup_tp1_before_sl"
MODEL_VERSION = "1.0.0"
MIN_TRAIN = 300
MIN_TEST = 100
MAX_ECE = 0.05
ASSET_CLASSES = ["FOREX", "CRYPTO", "INDICES", "COMMODITIES"]
LABEL_DEFINITION = "1 if the first target (TP1) was reached before the stop on a filled setup, else 0"


class ReliabilityBin(BaseModel):
    lower: float
    upper: float
    mean_predicted: float | None
    observed_frequency: float | None
    count: int


class ModelScores(BaseModel):
    name: str
    brier: float
    ece: float
    auc: float | None


class CalibrationReport(BaseModel):
    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION
    status: str  # CALIBRATED | NOT_CALIBRATED | INSUFFICIENT_DATA
    trained_at: str
    data_mode: str
    label_definition: str = LABEL_DEFINITION
    n_total: int
    n_train: int = 0
    n_calibration: int = 0
    n_test: int = 0
    base_rate: float | None = None
    brier: float | None = None
    brier_baseline: float | None = None
    brier_skill: float | None = None
    ece: float | None = None
    auc: float | None = None
    reliability: list[ReliabilityBin] = Field(default_factory=list)
    challenger: ModelScores | None = None
    reasons: list[str] = Field(default_factory=list)
    test_period: tuple[str, str] | None = None


def features_for(
    vector: list[float], direction: str, score: float, rr: float, regime: str, asset_class: str
) -> list[float]:
    row = [*vector, 1.0 if direction == "LONG" else -1.0, score / 100.0, min(rr, 10.0) / 5.0]
    row += [1.0 if regime == r.value else 0.0 for r in REGIME_CODES]
    row += [1.0 if asset_class == a else 0.0 for a in ASSET_CLASSES]
    return row


def _xy(records: list[SetupRecord]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(
        [
            features_for(r.vector, r.direction, r.score, r.effective_rr, r.regime, r.asset_class)
            for r in records
        ]
    )
    y = np.asarray([1 if r.outcome.tp1_before_sl else 0 for r in records])
    return x, y


def expected_calibration_error(
    p: np.ndarray, y: np.ndarray, bins: int = 10
) -> tuple[float, list[ReliabilityBin]]:
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    out: list[ReliabilityBin] = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < bins - 1 else (p >= lo) & (p <= hi)
        cnt = int(mask.sum())
        if cnt:
            mp, fy = float(p[mask].mean()), float(y[mask].mean())
            ece += cnt / len(p) * abs(mp - fy)
            out.append(
                ReliabilityBin(
                    lower=round(lo, 2),
                    upper=round(hi, 2),
                    mean_predicted=round(mp, 4),
                    observed_frequency=round(fy, 4),
                    count=cnt,
                )
            )
        else:
            out.append(
                ReliabilityBin(
                    lower=round(lo, 2),
                    upper=round(hi, 2),
                    mean_predicted=None,
                    observed_frequency=None,
                    count=0,
                )
            )
    return round(float(ece), 4), out


class SetupProbabilityModel:
    def __init__(self) -> None:
        self.scaler: StandardScaler | None = None
        self.model: LogisticRegression | None = None
        self.iso: IsotonicRegression | None = None
        self.report: CalibrationReport | None = None

    @property
    def calibrated(self) -> bool:
        return self.report is not None and self.report.status == "CALIBRATED"

    def fit(self, records: list[SetupRecord], data_mode: str) -> CalibrationReport:
        now = datetime.now(UTC).isoformat()
        usable = sorted(
            [r for r in records if r.filled and r.outcome.tp1_before_sl is not None],
            key=lambda r: r.timestamp,
        )
        n = len(usable)
        need = int((MIN_TRAIN + MIN_TEST) / 0.8)
        if n < need:
            self.report = CalibrationReport(
                status="INSUFFICIENT_DATA",
                trained_at=now,
                data_mode=data_mode,
                n_total=n,
                reasons=[f"Need at least {need} labelled setups, have {n}"],
            )
            self.model = None
            return self.report
        i_tr, i_cal = int(n * 0.6), int(n * 0.8)
        tr, cal, te = usable[:i_tr], usable[i_tr:i_cal], usable[i_cal:]
        xtr, ytr = _xy(tr)
        xcal, ycal = _xy(cal)
        xte, yte = _xy(te)
        reasons: list[str] = []
        if len(set(ytr)) < 2:
            self.report = CalibrationReport(
                status="NOT_CALIBRATED",
                trained_at=now,
                data_mode=data_mode,
                n_total=n,
                reasons=["Training labels contain a single class"],
            )
            return self.report
        scaler = StandardScaler().fit(xtr)
        model = LogisticRegression(max_iter=2000, C=0.5).fit(scaler.transform(xtr), ytr)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
            model.predict_proba(scaler.transform(xcal))[:, 1], ycal
        )
        p = iso.predict(model.predict_proba(scaler.transform(xte))[:, 1])
        base = float(ytr.mean())
        brier = float(np.mean((p - yte) ** 2))
        brier0 = float(np.mean((base - yte) ** 2))
        skill = 1 - brier / brier0 if brier0 > 0 else 0.0
        ece, rel = expected_calibration_error(p, yte)
        auc = float(roc_auc_score(yte, p)) if len(set(yte)) > 1 else None

        challenger = None
        try:
            hgb = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05).fit(xtr, ytr)
            iso2 = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
                hgb.predict_proba(xcal)[:, 1], ycal
            )
            p2 = iso2.predict(hgb.predict_proba(xte)[:, 1])
            ece2, _ = expected_calibration_error(p2, yte)
            challenger = ModelScores(
                name="HistGradientBoosting + isotonic",
                brier=round(float(np.mean((p2 - yte) ** 2)), 4),
                ece=ece2,
                auc=round(float(roc_auc_score(yte, p2)), 4) if len(set(yte)) > 1 else None,
            )
        except ValueError as exc:
            reasons.append(f"Challenger not evaluated: {exc}")

        if len(tr) < MIN_TRAIN:
            reasons.append(f"Training set {len(tr)} < {MIN_TRAIN}")
        if len(te) < MIN_TEST:
            reasons.append(f"Test set {len(te)} < {MIN_TEST}")
        if ece > MAX_ECE:
            reasons.append(f"Expected calibration error {ece:.3f} > {MAX_ECE}")
        if skill <= 0:
            reasons.append(f"No Brier skill over the base rate ({skill:+.3f})")
        status = (
            "CALIBRATED" if not [r for r in reasons if not r.startswith("Challenger")] else "NOT_CALIBRATED"
        )
        self.scaler, self.model, self.iso = scaler, model, iso
        self.report = CalibrationReport(
            status=status,
            trained_at=now,
            data_mode=data_mode,
            n_total=n,
            n_train=len(tr),
            n_calibration=len(cal),
            n_test=len(te),
            base_rate=round(base, 4),
            brier=round(brier, 4),
            brier_baseline=round(brier0, 4),
            brier_skill=round(skill, 4),
            ece=ece,
            auc=round(auc, 4) if auc is not None else None,
            reliability=rel,
            challenger=challenger,
            reasons=reasons or ["Passed out-of-sample calibration checks"],
            test_period=(te[0].timestamp, te[-1].timestamp),
        )
        return self.report

    def predict(
        self, vector: list[float], direction: str, score: float, rr: float, regime: str, asset_class: str
    ) -> float | None:
        """Calibrated probability, or None when the model has not passed validation."""
        if not self.calibrated or self.model is None or self.scaler is None or self.iso is None:
            return None
        x = np.asarray([features_for(vector, direction, score, rr, regime, asset_class)])
        raw = self.model.predict_proba(self.scaler.transform(x))[:, 1]
        return round(float(self.iso.predict(raw)[0]), 4)
