import json
from pathlib import Path

import pandas as pd

from app.data.loaders import get_data
from app.leads import features
from app.leads.propensity import MODEL_PATH, score

L = get_data().leads


def test_model_and_auc():
    assert MODEL_PATH.exists()
    import joblib
    assert joblib.load(MODEL_PATH)["metrics"]["lr"]["auc"] > 0.6


def test_no_leakage_features():
    assert not set(features.FEATURES) & set(features.LEAKY)
    X = features.build_features(L)
    assert list(X.columns) == features.FEATURES


def test_score_shape_and_direction():
    good = L[(L.has_gstin) & (L.segment == "Professional offices")].iloc[0]
    bad = L[(~L.has_gstin) & (L.segment == "Micro retail & services")].iloc[0]
    pg, rg = score(pd.DataFrame([good]))
    pb, rb = score(pd.DataFrame([bad]))
    assert 0 < pb < pg < 1
    assert len(rg) == 3 and len(rb) == 3
    assert all(r.endswith(("↑", "↓")) for r in rg + rb)
