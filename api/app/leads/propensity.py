"""score(features) -> (prob, top-3 plain-text reasons)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.config import API_ROOT
from app.leads.features import FEATURES, build_features

MODEL_PATH = (API_ROOT / ".." / "data" / "derived" / "propensity.joblib").resolve()

_NUM_LABEL = {"employee_count_log": "Team size", "num_sites": "Number of sites",
              "telecom_spend_log": "Telecom spend", "n_interest": "Products asked about"}
_CAT_LABEL = {"has_gstin_c": "GSTIN", "has_udyam_c": "Udyam", "city_tier_c": "Tier", "segment": "",
              "lead_source": "Source:", "current_internet": "Uses", "business_type": "",
              "preferred_language": "Language:", "annual_turnover_band": "Turnover"}


@lru_cache(maxsize=1)
def _load():
    return joblib.load(MODEL_PATH)


def _label(feat: str, value_name: str | None, sign: int) -> str:
    arrow = "↑" if sign > 0 else "↓"
    if value_name is None:
        return f"{_NUM_LABEL.get(feat, feat)} {arrow}"
    if feat == "has_gstin_c":
        return ("Has GSTIN" if value_name == "Y" else "No GSTIN") + f" {arrow}"
    if feat == "has_udyam_c":
        return ("Has Udyam" if value_name == "Y" else "No Udyam") + f" {arrow}"
    if feat == "city_tier_c":
        return f"Tier-{value_name} city {arrow}"
    return f"{_CAT_LABEL.get(feat, '')} {value_name} {arrow}".replace("  ", " ").strip()


def score(row: pd.DataFrame | dict, top_k: int = 3) -> tuple[float, list[str]]:
    """row: one-row DataFrame/dict of RAW lead columns (as in smb_leads) -> (prob, reasons)."""
    bundle = _load()
    pipe = bundle["pipeline"]
    df = pd.DataFrame([row]) if isinstance(row, dict) else row.iloc[[0]]
    X = build_features(df)
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
