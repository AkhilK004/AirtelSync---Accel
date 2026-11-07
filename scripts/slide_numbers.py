"""Numbers quoted in docs/slides_outline.md, computed from data + the engine (no invented figures). Run: cd api && python -m uv run python ../scripts/slide_numbers.py"""
import json, sys
sys.path.insert(0, ".")
import pandas as pd
from app.data.loaders import get_data
from app.engine.pricing import make_quote
from app.models.engine import Profile

L = get_data().leads
A = L[L.activated]
out = {}
seg = L.groupby("segment").agg(leads=("lead_id", "size"), activated=("activated", "sum"), cost=("acquisition_cost_inr", "sum"))
seg["act_rate_pct"] = (100 * seg.activated / seg.leads).round(1)
seg["cost_per_activation"] = (seg.cost / seg.activated).round(0)
seg["median_monthly_value"] = A.groupby("segment").monthly_bundle_value_inr.median()
seg["median_setup"] = A.groupby("segment").one_time_setup_inr.median()
seg["churn_pct"] = (100 * A.groupby("segment").churned_within_6_months.mean()).round(1)
seg["payback_months_revenue"] = (seg.cost_per_activation / seg.median_monthly_value).round(1)
out["segments"] = seg.drop(columns="cost").reset_index().to_dict("records")
src = L.groupby("lead_source").agg(leads=("lead_id", "size"), activated=("activated", "sum"), cost=("acquisition_cost_inr", "sum"))
src["cost_per_activation"] = (src.cost / src.activated).round(0)
src["act_rate_pct"] = (100 * src.activated / src.leads).round(1)
out["sources"] = src.drop(columns="cost").reset_index().to_dict("records")
out["blended"] = {"cac": round(L.acquisition_cost_inr.sum() / len(A)), "median_value": float(A.monthly_bundle_value_inr.median()), "avg_days": round(A.days_lead_to_activation.mean(), 1),
                  "calls": round(A.customer_follow_up_calls.mean(), 2)}
prof = {"Dukaan Starter (kirana, 2 staff, tier 2)": dict(business_type="Kirana store", employees=2, locations=1, city_tier=2, gstin_status="active"),
        "Pro Office (clinic, 6 staff, tier 1)": dict(business_type="Dental clinic", employees=6, locations=1, city_tier=1, gstin_status="active"),
        "Multi-Site Connect (4 restaurants, 40 staff)": dict(business_type="Restaurant chain", employees=40, locations=4, city_tier=1, gstin_status="active"),
        "Factory Connect (auto parts, 80 staff)": dict(business_type="Auto-parts unit", employees=80, locations=1, city_tier=1, gstin_status="active")}
out["bundles"] = {}
for name, p in prof.items():
    _, q = make_quote(Profile(**p))
    out["bundles"][name] = {"monthly_ex_gst": q.monthly_subtotal_display, "monthly_incl_gst": q.monthly_total_display, "setup_incl_gst": q.one_time_total_display,
                            "contract_months": q.contract_months, "lines": [f"{l.name} x{l.qty}" for l in q.lines]}
json.dump(out, open("../docs/slide_numbers.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:5000])
