"""Propensity v2: leakage, train/serve parity and the quality gates from docs/model_card.md (read from the trained artefact)."""
import pandas as pd
import pytest

from app.data.loaders import get_data
from app.leads import features, scoring
from app.leads.propensity import MODEL_PATH, _load, model_info, score

L = get_data().leads


@pytest.fixture(scope="module")
def m():
    assert MODEL_PATH.exists(), "run scripts/train_propensity.py"
    return _load()["metrics"]


def test_no_leakage_features():
    assert not set(features.FEATURES) & set(features.LEAKY)
    assert not set(features.RAW_INPUTS) & set(features.LEAKY)
    X = features.build_features(L)
    assert list(X.columns) == features.FEATURES and not X.isna().any().any()


def test_excluded_features_stay_out():
    for f in ("business_type", "preferred_language", "annual_turnover_band", "has_udyam_c", "telecom_spend_log", "n_interest"):
        assert f not in features.FEATURES


# ------------------------------------------------------------------ quality gates (fail the build on a worse model)
def test_gate_discrimination(m):
    assert m["nested_cv"]["auc_mean"] >= 0.70
    assert m["time_holdout"]["auc_ci95"][0] > 0.65


def test_gate_not_overfitting(m):
    assert m["nested_cv"]["overfit_gap"] <= 0.04


def test_gate_not_underfitting(m):
    curve = [p["cv_auc"] for p in m["learning_curve"]]
    assert curve[-1] >= curve[0]                       # more data never hurts -> model has capacity to use it
    assert m["time_holdout"]["brier"] < m["time_holdout"]["brier_base_rate_only"]  # beats "predict the base rate"


def test_gate_calibrated(m):
    assert m["time_holdout"]["ece_decile"] <= 0.03


def test_gate_no_leak_through_pipeline(m):
    assert 0.45 <= m["shuffled_label_auc"] <= 0.55


def test_gate_beats_previous_model(m):
    assert m["paired_vs_v1"]["delta_auc_mean"] > 0 and m["paired_vs_v1"]["share_folds_v2_better"] >= 0.8


# ------------------------------------------------------------------ stage-aware gates (A64)
def test_gate_stage_models_beat_all_leads_model(m):
    sm = m["stage_models"]
    assert set(sm) == {"1", "2", "3", "4"}
    for k, s in sm.items():
        assert s["auc"] >= s["auc_global"] - 0.01, k              # never worse at ranking within the stage
        assert s["brier"] < s["brier_base"] + 1e-4, k             # beats "predict the stage base rate"
        assert s["brier"] <= s["brier_global"], k                 # better calibrated than scoring everyone as a new lead
        assert s["ece"] <= 0.10, k
    assert sm["3"]["ece"] < 0.5 * sm["3"]["ece_global"] and sm["4"]["ece"] < 0.5 * sm["4"]["ece_global"]


def test_stage_scores_are_comparable_across_stages():
    row = L[(L.has_gstin) & (L.segment == "Professional offices")].iloc[[0]]
    probs = [score(row, stage=s)[0] for s in ("advisor", "quote", "kyc", "order")]
    assert probs == sorted(probs) and probs[-1] > 0.4 > probs[0]   # later stage -> higher P(activate); KYC-complete ~60%, not ~8%
    assert score(row, stage=None)[0] < probs[1]                      # new-lead score stays low
    assert score(row, stage="nonsense")[0] == score(row, stage=None)[0]


# ------------------------------------------------------------------ train/serve parity
def test_serving_row_provides_every_model_input():
    ctx = dict(business_type="Pharmacy", employees=6, locations=1, city_tier=1, language="hi", tools=["Accel mobile"], wants=[],
               channel=None, segment="micro_retail", partner_code=None, has_gstin=True)
    row = scoring.raw_row(ctx)
    assert set(features.RAW_INPUTS) <= set(row)
    X = features.build_features(pd.DataFrame([row]))
    assert list(X.columns) == features.FEATURES and not X.isna().any().any()
    assert X.iloc[0]["accel_existing"] == "Y"
    seen = features.build_features(L)
    assert all(X.iloc[0][c] in set(seen[c]) for c in features.CATEGORICAL)  # only categories seen in training


def test_score_shape_and_direction():
    good = L[(L.has_gstin) & (L.segment == "Professional offices")].iloc[0]
    bad = L[(~L.has_gstin) & (L.segment == "Micro retail & services")].iloc[0]
    pg, rg = score(pd.DataFrame([good]))
    pb, rb = score(pd.DataFrame([bad]))
    assert 0 < pb < pg < 1
    assert len(rg) == 3 and len(rb) == 3
    assert all(r.endswith(("↑", "↓")) for r in rg + rb)


def test_accel_customer_scores_higher():
    base = dict(business_type="Clinic", employees=6, locations=1, city_tier=1, language="en", wants=[], channel=None,
                segment="professional_office", partner_code=None, has_gstin=True)
    hi, _ = score(pd.DataFrame([scoring.raw_row({**base, "tools": ["Accel mobile"]})]))
    lo, _ = score(pd.DataFrame([scoring.raw_row({**base, "tools": []})]))
    assert hi > lo


def test_model_info_for_health():
    info = model_info()
    assert info["loaded"] and info["version"] == "propensity-v3" and info["stages"] == ["1", "2", "3", "4"] and info["features"] == features.FEATURES and info["cv_auc"] >= 0.70
