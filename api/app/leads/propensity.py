"""score(features) -> (prob, top-3 plain-text reasons)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.config import API_ROOT
from app.leads.features import FEATURES, build_features

# Back-office lead stage -> funnel stage the lead has already reached (index into the CSV funnel; A64). Same mapping as app/seed.py STAGE.
STAGE_REACHED = {"advisor": 1, "quote": 2, "kyc": 3, "order": 4}  # 1 Contacted, 2 Needs assessed, 3 Quote accepted, 4 KYC complete

MODEL_PATH = (API_ROOT / ".." / "data" / "derived" / "propensity.joblib").resolve()

_NUM_LABEL = {"employee_count_log": "Team size", "num_sites": "Number of sites"}
_CAT_LABEL = {"has_gstin_c": "GSTIN", "city_tier_c": "Tier", "segment": "", "lead_source": "Source:", "current_internet": "Uses", "accel_existing": "Accel"}


@lru_cache(maxsize=1)
def _load():
    return joblib.load(MODEL_PATH)


def model_info() -> dict:
    """Version + headline metrics for /health and the model card (no data rows)."""
    try:
        b = _load()
    except FileNotFoundError:
        return {"loaded": False}
    m = b.get("metrics", {})
    return {"loaded": True, "version": b.get("model_version", "propensity-v1"), "trained_at": b.get("trained_at"), "n_rows": b.get("n_rows"),
            "features": b.get("features"), "stages": sorted(b.get("stage_pipelines", {}) or []), "cv_auc": m.get("nested_cv", {}).get("auc_mean"), "holdout_auc": m.get("time_holdout", {}).get("auc"),
            "ece": m.get("time_holdout", {}).get("ece_decile")}


def _label(feat: str, value_name: str | None, sign: int) -> str:
    arrow = "↑" if sign > 0 else "↓"
    if value_name is None:
        return f"{_NUM_LABEL.get(feat, feat)} {arrow}"
    if value_name == "infrequent_sklearn":  # pooled rare categories (min_frequency)
        value_name = "other"
    if feat == "accel_existing":
        return ("Existing Accel customer" if value_name == "Y" else "Not with Accel today") + f" {arrow}"
    if feat == "has_gstin_c":
        return ("Has GSTIN" if value_name == "Y" else "No GSTIN") + f" {arrow}"
    if feat == "city_tier_c":
        return f"Tier-{value_name} city {arrow}"
    return f"{_CAT_LABEL.get(feat, '')} {value_name} {arrow}".replace("  ", " ").strip()


def score(row: pd.DataFrame | dict, top_k: int = 3, stage: str | None = None) -> tuple[float, list[str]]:
    """row: one-row DataFrame/dict of RAW lead columns (as in smb_leads) -> (P(activate), reasons).
    stage=None: probability for a brand-new lead. stage in STAGE_REACHED: probability given the lead already reached that funnel stage
    (stage-aware model, A64), so a lead at KYC is scored ~60%, not ~8%, and expected values compare across stages."""
    bundle = _load()
    df = pd.DataFrame([row]) if isinstance(row, dict) else row.iloc[[0]]
    X = build_features(df)
    if stage in STAGE_REACHED and bundle.get("stage_pipelines"):
        pipe = bundle["stage_pipelines"][str(STAGE_REACHED[stage])]  # trained without class weights: already calibrated
        prob = float(pipe.predict_proba(X)[0, 1])
    else:
        pipe = bundle["pipeline"]
        raw = float(pipe.predict_proba(X)[0, 1])
        pi = bundle["prior"]  # undo class_weight="balanced" prior shift so prob is calibrated
        prob = float(1 / (1 + np.exp(-(np.log(raw / (1 - raw)) - np.log((1 - pi) / pi)))))
    pre, clf = pipe.named_steps["pre"], pipe.named_steps["clf"]
    xt = pre.transform(X)
    xt = xt.toarray() if hasattr(xt, "toarray") else np.asarray(xt)
    contrib = xt[0] * clf.coef_[0]
    names = pre.get_feature_names_out()
    order = np.argsort(-np.abs(contrib))
    reasons: list[str] = []
    for i in order:
        if abs(contrib[i]) < 1e-6:
            continue
        n = names[i]
        if n.startswith("cat__"):
            body = n[5:]
            feat = next(f for f in FEATURES if body.startswith(f + "_"))
            reasons.append(_label(feat, body[len(feat) + 1:], 1 if contrib[i] > 0 else -1))
        else:
            reasons.append(_label(n.split("__", 1)[1], None, 1 if contrib[i] > 0 else -1))
        if len(reasons) == top_k:
            break
    return prob, reasons
