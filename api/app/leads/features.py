"""Feature schema for propensity: ONLY facts known at lead creation / after advisor chat (no leakage)."""
CATEGORICAL = ["segment", "business_type", "city_tier_c", "lead_source", "preferred_language",
               "current_internet", "annual_turnover_band", "has_gstin_c", "has_udyam_c"]
NUMERIC = ["employee_count_log", "num_sites", "telecom_spend_log", "n_interest"]
FEATURES = CATEGORICAL + NUMERIC
# Explicitly excluded (leakage): stage_reached, outcome, drop_reason, *_date after creation,
# days_lead_to_activation, follow-up calls, bundle_*, value, setup, contract, churn, nps, acquisition cost.
LEAKY = ["stage_reached", "outcome", "drop_reason", "contacted_date", "needs_assessed_date", "quote_accepted_date",
         "kyc_complete_date", "activated_date", "days_lead_to_activation", "customer_follow_up_calls",
         "bundle_products", "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months",
         "churned_within_6_months", "nps_score", "acquisition_cost_inr"]

import numpy as np
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["segment"] = df["segment"]
    x["business_type"] = df["business_type"]
    x["city_tier_c"] = df["city_tier"].astype(str)
    x["lead_source"] = df["lead_source"]
    x["preferred_language"] = df["preferred_language"]
    x["current_internet"] = df["current_internet"].fillna("Unknown")
    x["annual_turnover_band"] = df["annual_turnover_band"]
    x["has_gstin_c"] = np.where(df["has_gstin"].astype(bool), "Y", "N")
    x["has_udyam_c"] = np.where(df["has_udyam"].astype(bool), "Y", "N")
    x["employee_count_log"] = np.log1p(df["employee_count"])
    x["num_sites"] = df["num_sites"]
    x["telecom_spend_log"] = np.log1p(df["monthly_telecom_spend_inr"])
    x["n_interest"] = df["products_of_interest"].fillna("").map(lambda s: len([p for p in s.split(";") if p]))
    return x[FEATURES]
