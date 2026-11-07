"""Feature schema for propensity: ONLY facts we also have when a live lead is scored (no leakage, no train/serve skew).

v2 (docs/assumptions.md A59): every feature below is either asked by the advisor, derived from the channel, or (accel_existing)
offered as a quick-reply chip. Features that were only imputed at serving time were dropped; tests show no loss of AUC from that.
"""
CATEGORICAL = ["segment", "city_tier_c", "lead_source", "current_internet", "has_gstin_c", "accel_existing"]
NUMERIC = ["employee_count_log", "num_sites"]
FEATURES = CATEGORICAL + NUMERIC
# Raw lead columns (smb_leads.csv names) that build_features reads. scoring.raw_row must provide all of them.
RAW_INPUTS = ["segment", "city_tier", "lead_source", "current_internet", "has_gstin", "current_provider", "employee_count", "num_sites"]

# Explicitly excluded (leakage): stage_reached, outcome, drop_reason, *_date after creation,
# days_lead_to_activation, follow-up calls, bundle_*, value, setup, contract, churn, nps, acquisition cost.
LEAKY = ["stage_reached", "outcome", "drop_reason", "contacted_date", "needs_assessed_date", "quote_accepted_date",
         "kyc_complete_date", "activated_date", "days_lead_to_activation", "customer_follow_up_calls",
         "bundle_products", "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months",
         "churned_within_6_months", "nps_score", "acquisition_cost_inr"]
# Excluded by design in v2, with the measured reason (5x5 repeated CV, scripts/train_propensity.py output).
EXCLUDED_BY_DESIGN = {
    "business_type": "noise: ~60 values, already summarised by segment; dropping it raised CV AUC by ~0.02 (overfitting)",
    "preferred_language": "fairness: down-ranks Tamil/Punjabi/Kannada speakers on weak evidence (n=96-253); costs ~0.001 AUC",
    "annual_turnover_band": "never asked by the advisor -> would be a constant at serving time (train/serve skew)",
    "monthly_telecom_spend_inr": "never asked -> imputed at serving time (skew); no measurable AUC contribution",
    "has_udyam": "never asked -> always False at serving time (skew); no measurable AUC contribution",
    "products_of_interest": "advisor 'wants' are not the same thing as CSV product ids (skew); multi-hot version overfits",
    "state": "high cardinality; lowers CV AUC",
}

import numpy as np
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["segment"] = df["segment"]
    x["city_tier_c"] = df["city_tier"].astype(int).astype(str)
    x["lead_source"] = df["lead_source"]
    x["current_internet"] = df["current_internet"].fillna("Unknown")
    x["has_gstin_c"] = np.where(df["has_gstin"].astype(bool), "Y", "N")
    provider = df["current_provider"] if "current_provider" in df else pd.Series("", index=df.index)  # rows stored before v2 lack it
    x["accel_existing"] = np.where(provider.fillna("").astype(str).str.startswith("Accel"), "Y", "N")
    x["employee_count_log"] = np.log1p(df["employee_count"].astype(float))
    x["num_sites"] = df["num_sites"].astype(float)
    return x[FEATURES]
