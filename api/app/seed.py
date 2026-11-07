"""Demo seed: ~30 back-office leads from real smb_leads.csv rows (scored by the real model) + 3 live orders in different states.

All seeded events carry props.seed=true so the funnel panel can say which numbers are demo data.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import pandas as pd

from app import clock
from app.analytics import events as ev
from app.data.loaders import get_data
from app.engine.pricing import make_quote, new_id
from app.leads import service as leads
from app.leads.features import RAW_INPUTS
from app.models.engine import Profile
from app.orders import service as orders
from app.orders import state as S
from app.repo import get_repo
from app.routers.checkout import CheckoutBody, place_order

SEG_VALUE = {"Micro retail & services": "micro_retail", "Professional offices": "professional_office",
             "Small multi-site businesses": "multi_site", "Small manufacturers": "manufacturer"}
STAGE = {"Contacted": "advisor", "Needs assessed": "quote", "Quote accepted": "kyc", "KYC complete": "order"}
REASON = {
    "Price too high": "price", "Competitor offered cheaper plan": "price", "Quote too complex to understand": "price", "Quote took too long to arrive": "price",
    "Missing GST or Udyam document": "kyc_issue", "Document details did not match": "kyc_issue", "Found paperwork too long": "kyc_issue",
    "Authorised signatory not available": "kyc_issue", "Site not feasible for fibre": "needs_site_survey",
    "Owner had no time for a visit": "requested_human", "Visit not scheduled by sales": "requested_human",
    "Installation delayed beyond 21 days": "abandoned", "Customer cancelled before install": "abandoned", "First payment failed": "abandoned",
    "Locked in with current provider": "abandoned", "Only wanted a mobile plan": "abandoned", "Decided to wait": "abandoned",
}
RAW_COLS = RAW_INPUTS + ["business_type", "preferred_language"]  # model inputs + display-only fields for the drawer
STATUS_PLAN = ["contacted"] * 5 + ["won"] * 3 + ["lost"] * 2


def _py(v):
    return None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)


def _lead_sample(n_total: int = 30) -> pd.DataFrame:
    L = get_data().leads
    d = L[(~L.activated) & L.drop_reason.isin(REASON)]
    parts = [d[d.stage_reached == "Needs assessed"].sample(10, random_state=7), d[d.stage_reached == "Quote accepted"].sample(7, random_state=7),
             d[d.stage_reached == "KYC complete"].sample(5, random_state=7),
             d[d.segment.isin(["Small multi-site businesses", "Small manufacturers"]) & (d.stage_reached != "Needs assessed")].sample(8, random_state=7)]
    return pd.concat(parts).drop_duplicates("lead_id").head(n_total)


def _seed_leads() -> int:
    repo = get_repo()
    rng = random.Random(7)
    today = clock.now()
    rows = _lead_sample()
    for i, r in enumerate(rows.itertuples(index=False)):
        rd = r._asdict()
        raw = {c: _py(rd[c]) for c in RAW_COLS}
        seg = SEG_VALUE[rd["segment"]]
        reason = REASON[rd["drop_reason"]]
        stage = STAGE[rd["stage_reached"]]
        partner = leads.partner_for_city(rd["city"]) if rd["lead_source"] == "Channel partner" else None
        route, code = leads.route_for(seg, partner, rd["city"], assisted=reason == "needs_site_survey")
        if route == "telesales" and rd["lead_source"] == "Channel partner":
            route, code = "partner", "PRT-WEST-02"  # attribution kept even when the partner's city list does not cover the lead
        lid = new_id()
        repo.put("leads", lid, {
            "id": lid, "created_at": (today - timedelta(hours=rng.randint(2, 140))).isoformat(timespec="seconds"), "session_id": None,
            "profile": {"business_name": rd["business_name"], "business_type": rd["business_type"]}, "raw_features": raw, "city": rd["city"], "segment": seg,
            "stage_reached": stage, "reason": reason, "quote_id": None, "order_id": None, "score": None, "score_reasons": [], "route_to": route,
            "partner_code": code, "status": STATUS_PLAN[i] if i < len(STATUS_PLAN) else "new", "seed_lead_id": rd["lead_id"],
        })
        ref = f"seed-{lid}"
        ev.log_event("advisor_started", ref, {"channel": "seed"})
        if stage != "advisor":
            ev.log_event("recommendation_shown", ref, {"segment": seg})
        if stage in ("kyc", "order"):
            ev.log_event("quote_accepted", f"seedq-{lid}", {})
            ev.log_event("checkout_completed", f"seedo-{lid}", {})
            ev.log_event("kyc_decided", f"seedo-{lid}", {"decision": "APPROVED" if stage == "order" else "ACTION_REQUIRED", "codes": []})
        if reason == "requested_human" or reason == "needs_site_survey":
            ev.log_event("handoff_requested", ref, {"reason": reason})
    return len(rows)


def _spread(o: dict, start_days_ago: float, end_days_ago: float) -> None:
    """Re-date an order's events across [start, end] days ago so time-to-activate is meaningful in the demo."""
    now = clock.now()
    n = max(1, len(o["events"]) - 1)
    for i, e in enumerate(o["events"]):
        days = start_days_ago - (start_days_ago - end_days_ago) * i / n
        e["ts"] = (now - timedelta(days=days)).isoformat(timespec="seconds")
    o["created_at"] = o["events"][0]["ts"]


def _demo_order(profile: dict, business: str, phone: str, label: str) -> dict:
    repo = get_repo()
    state, quote = make_quote(Profile(**profile))
    repo.put("quotes", state.id, state.model_dump(mode="json"))
    slot = (clock.today() + timedelta(days=3)).isoformat()
    r = place_order(CheckoutBody(quote_id=state.id, phone=phone, otp="123456", business_name=business, address="14 Demo Road, Demo Nagar",
                                 slot_date=slot, slot_window="morning", payment_mode="pay_on_activation", language="en"))
    return {"id": r["order_id"], "last4": phone[-4:], "label": label, "quote_id": state.id}


def _seed_orders() -> list[dict]:
    repo = get_repo()
    out = []
    # 1) documents need fixing
    d = _demo_order({"business_type": "Pharmacy", "employees": 3, "locations": 1, "city_tier": 2, "gstin_status": "active"}, "Demo Pharmacy · action needed", "9999900001", "KYC action required")
    o = repo.get("orders", d["id"])
    orders.transition(o, S.KYC_PENDING)
    o = orders.transition(repo.get("orders", d["id"]), S.KYC_ACTION_REQUIRED)
    _spread(o, 3, 2.9); repo.put("orders", d["id"], o)
    out.append(d)
    # 2) technician assigned
    d = _demo_order({"business_type": "Dental clinic", "employees": 6, "locations": 1, "city_tier": 1, "gstin_status": "active"}, "Demo Dental Clinic · install soon", "9999900002", "Technician assigned")
    for _ in range(3):
        orders.advance(d["id"])
    o = repo.get("orders", d["id"]); _spread(o, 5, 1); repo.put("orders", d["id"], o)
    out.append(d)
    # 3) fully active
    d = _demo_order({"business_type": "CA firm", "employees": 12, "locations": 1, "city_tier": 1, "gstin_status": "active"}, "Demo CA Firm · all live", "9999900003", "Active")
    for _ in range(5):
        orders.advance(d["id"])
    o = repo.get("orders", d["id"]); _spread(o, 9, 4); repo.put("orders", d["id"], o)
    out.append(d)
    for d_ in out:  # a few tracker views so "status checks per order" is not empty
        for _ in range({"Active": 1, "Technician assigned": 1}.get(d_["label"], 0)):
            ev.log_event("tracker_viewed", d_["id"], {})
    return out


def seed_demo(reset: bool = True) -> dict:
    repo = get_repo()
    if reset and hasattr(repo, "clear"):
        repo.clear()
    elif repo.list("meta"):
        return {"seeded": False, "reason": "already seeded"}
    ev.set_seeding(True)
    try:
        n = _seed_leads()
        demo = _seed_orders()
    finally:
        ev.set_seeding(False)
    repo.put("meta", "demo", {"orders": demo})
    return {"seeded": True, "leads": n, "demo_orders": [{"order_id": d["id"], "phone_last4": d["last4"], "label": d["label"]} for d in demo]}
