import base64
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import clock
from app.analytics.funnel import compute
from app.config import settings
from app.leads import scoring
from app.leads import service as leads
from app.main import app
from app.repo import get_repo
from app.seed import seed_demo
from tests.test_kyc_api import consent, run, upload

c = TestClient(app)
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{settings.BACKOFFICE_USER}:{settings.BACKOFFICE_PASSWORD}".encode()).decode()}
ADMIN = {"X-Admin-Token": settings.ADMIN_TOKEN}


@pytest.fixture()
def seeded():
    get_repo().clear()
    seed_demo(reset=True)
    yield
    get_repo().clear()


@pytest.fixture()
def empty():
    get_repo().clear()
    yield
    get_repo().clear()


def L(**params):
    return c.get("/backoffice/leads", params=params, headers=AUTH).json()["leads"]


# ------------------------------------------------------------------ auth
def test_basic_auth_required_everywhere(seeded):
    for path in ("/backoffice/leads", "/backoffice/funnel", "/backoffice/me"):
        r = c.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "BACKOFFICE_AUTH"
    bad = {"Authorization": "Basic " + base64.b64encode(b"admin:wrong").decode()}
    assert c.get("/backoffice/leads", headers=bad).status_code == 401
    assert c.get("/backoffice/me", headers=AUTH).json() == {"user": settings.BACKOFFICE_USER}


# ------------------------------------------------------------------ ranked list with reasons
def test_seed_creates_30_scored_leads_ranked_by_expected_value_with_reasons(seeded):
    rows = L()
    assert len(rows) == 31  # 30 seeded + the stuck KYC_ACTION_REQUIRED demo order, derived lazily after 24h
    assert sum(1 for r in rows if r["order_id"]) == 1
    scores = [r["score"] for r in rows]
    assert all(0 < s < 1 for s in scores)
    ev = [r["expected_value_paise"] for r in rows]
    assert ev == sorted(ev, reverse=True) and all(isinstance(v, int) for v in ev)  # A62: rank by expected monthly value
    assert all(r["expected_value_display"].startswith("₹") for r in rows)
    assert all((r["route"] == "compliance") == bool(r["compliance_hold"]) for r in rows)
    assert all(r["expected_value_paise"] == 0 for r in rows if r["compliance_hold"])
    assert all(len(r["score_reasons"]) == 3 and r["score_reasons"][0].endswith(("↑", "↓")) for r in rows)
    assert {r["reason"] for r in rows} >= {"price", "kyc_issue", "needs_site_survey"}
    assert all(r["name"] and r["route"] and r["age_hours"] > 0 and r["territory_team"] for r in rows)


def test_filters(seeded):
    all_rows = L()
    assert {r["route"] for r in L(route="field_sales")} == {"field_sales"}
    assert {r["segment"] for r in L(segment="multi_site")} == {"multi_site"}
    assert {r["stage"] for r in L(stage="kyc")} == {"kyc"}
    assert sum(len(L(route=q)) for q in ("partner", "field_sales", "telesales", "compliance")) == len(all_rows)
    assert {r["status"] for r in L(status="won")} == {"won"} and len(L(status="won")) == 3
    assert L(route="field_sales", segment="micro_retail") == []


def test_routing_rules(seeded):
    for r in L():
        if r["segment"] in ("multi_site", "manufacturer") and not r["compliance_hold"]:
            assert r["route"] == "field_sales"
        if r["route"] == "partner":
            assert r["partner_code"]
    assert leads.route_for("micro_retail", None, "Lucknow") == ("partner", "PRT-NORTH-01")     # partner owns its cities
    assert leads.route_for("micro_retail", "PRT-X", "Mumbai") == ("partner", "PRT-X")          # attribution by code
    assert leads.route_for("micro_retail", None, "Mumbai") == ("telesales", None)
    assert leads.route_for("manufacturer", "PRT-X", "Lucknow") == ("field_sales", "PRT-X")     # field force wins, attribution kept
    assert leads.route_for("micro_retail", None, "Mumbai", assisted=True)[0] == "field_sales"
    assert leads.team_for_city("Pune") == "West" and leads.team_for_city("Chennai") == "South" and leads.team_for_city(None) == "Unassigned"


def test_compliance_hold_overrides_the_model():
    """A61: Cancelled/Suspended GSTIN -> compliance desk, expected value 0, whatever the score."""
    from app.data.loaders import get_data
    d = get_data()
    status = d.leads.gstin.map(lambda g: d.gstin[g].status if isinstance(g, str) and g in d.gstin else None)
    for want, code in (("Cancelled", "gstin_cancelled"), ("Suspended", "gstin_suspended"), ("Active", None)):
        lid = d.leads.loc[status == want, "lead_id"].iloc[0]
        assert leads.compliance_hold({"seed_lead_id": lid}) == code
    assert leads.compliance_hold({"id": "x"}) is None
    assert leads.expected_value_paise({"score": 0.5, "segment": "micro_retail", "compliance_hold": "gstin_cancelled"}) == 0
    micro = d.segment_median_bundle_value()["Micro retail & services"]
    assert leads.expected_value_paise({"score": 0.5, "segment": "micro_retail"}) == int(round(0.5 * micro)) * 100


def test_status_change_is_audited_and_validated(seeded):
    lid = L(status="new")[0]["id"]
    r = c.post(f"/backoffice/leads/{lid}/status", json={"status": "contacted"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "contacted"
    assert any(a["action"] == "lead_status" and a["order_id"] == lid and a["actor"] == settings.BACKOFFICE_USER for a in get_repo().list("audit_log"))
    assert c.post(f"/backoffice/leads/{lid}/status", json={"status": "nope"}, headers=AUTH).status_code == 422
    assert c.post("/backoffice/leads/missing/status", json={"status": "won"}, headers=AUTH).status_code == 404
    assert c.post(f"/backoffice/leads/{lid}/status", json={"status": "won"}).status_code == 401


def test_detail_has_profile_and_score_reasons(seeded):
    d = c.get(f"/backoffice/leads/{L()[0]['id']}", headers=AUTH).json()
    assert d["profile"]["business_type"] and d["profile"]["employees"] and len(d["score_reasons"]) == 3
    assert c.get("/backoffice/leads/missing", headers=AUTH).status_code == 404


# ------------------------------------------------------------------ leads created by the live journey
def test_advisor_handoff_lead_is_scored_routed_and_shown(empty):
    sid = c.post("/advisor/sessions", json={"partner_code": "PRT-ABC"}).json()["session_id"]
    r = c.post(f"/advisor/sessions/{sid}/messages", json={"text": "Retail chain with 12 stores in Mumbai, 60 staff, GST yes"}).json()
    assert r["handoff"]
    rows = L()
    assert len(rows) == 1 and rows[0]["route"] == "field_sales" and rows[0]["partner_code"] == "PRT-ABC" and rows[0]["reason"] == "needs_site_survey"
    assert rows[0]["score"] and rows[0]["segment"] == "multi_site"
    d = c.get(f"/backoffice/leads/{rows[0]['id']}", headers=AUTH).json()
    assert d["quote"]["bundle"] == "Multi-Site Connect" and d["quote"]["lines"]


def test_abandoned_and_unaccepted_leads_are_derived_lazily_and_idempotently(empty, monkeypatch):
    s1 = c.post("/advisor/sessions", json={}).json()["session_id"]
    c.post(f"/advisor/sessions/{s1}/messages", json={"text": "Salon"})                                                   # abandoned mid-chat
    s2 = c.post("/advisor/sessions", json={}).json()["session_id"]
    c.post(f"/advisor/sessions/{s2}/messages", json={"text": "Kirana store in Jaipur, 2 staff, 1 shop, GST yes"})        # saw a quote, never ordered
    assert L() == []                                                                                                    # not stale yet (10 min rule)
    later = clock.now() + timedelta(minutes=settings.ABANDON_MINUTES + 1)
    monkeypatch.setattr(leads.clock, "now", lambda: later)
    by_reason = {r["reason"]: r for r in L()}
    assert set(by_reason) == {"abandoned", "quote_not_accepted"} and by_reason["abandoned"]["stage"] == "advisor" and by_reason["quote_not_accepted"]["stage"] == "quote"
    assert leads.refresh() == 0 and len(L()) == 2


def test_session_that_became_an_order_is_not_a_lead(empty, monkeypatch):
    sid = c.post("/advisor/sessions", json={}).json()["session_id"]
    r = c.post(f"/advisor/sessions/{sid}/messages", json={"text": "Kirana store in Jaipur, 2 staff, 1 shop, GST yes"}).json()
    from tests.test_orders import SLOT
    c.post("/checkout", json=dict(quote_id=r["quote_id"], phone="9876543210", otp="123456", business_name="Ravi Kirana", address="12 Market Road, Jaipur",
                                  slot_date=SLOT, slot_window="morning", payment_mode="pay_on_activation", language="en"))
    later = clock.now() + timedelta(hours=1)
    monkeypatch.setattr(leads.clock, "now", lambda: later)
    assert L() == []


def test_kyc_issue_leads_manual_review_immediately_action_required_after_24h(empty, monkeypatch):
    oid_review, _ = run("K07")
    oid_fix, _ = run("K11")
    rows = L()
    assert [r["reason"] for r in rows] == ["kyc_issue"] and rows[0]["order_id"] == oid_review                            # only the manual-review one so far
    later = clock.now() + timedelta(hours=leads.KYC_STUCK_HOURS + 1)
    monkeypatch.setattr(leads.clock, "now", lambda: later)
    assert {r["order_id"] for r in L()} == {oid_review, oid_fix}
    d = c.get(f"/backoffice/leads/{next(r['id'] for r in L() if r['order_id'] == oid_review)}", headers=AUTH).json()
    assert d["kyc"]["decision"]["status"] == "MANUAL_REVIEW" and any(i["code"] == "CERT_VS_REGISTRY" for i in d["kyc"]["issues"])
    assert d["order"]["state"] == "KYC_REVIEW"


def test_callback_requests_become_leads(empty):
    from tests.test_orders import order
    oid = order()
    c.post(f"/orders/{oid}/callback", json={"phone_last4": "3210"})
    rows = L()
    assert rows[0]["reason"] == "callback_requested" and rows[0]["score"] is not None


# ------------------------------------------------------------------ scoring inputs
def test_scoring_features_and_direction():
    base = dict(business_type="Pharmacy", employees=6, locations=1, city_tier=1, language="hi", tools=[], wants=[], channel=None, segment="micro_retail", partner_code=None)
    r = scoring.raw_row({**base, "has_gstin": True, "tools": ["Mobile hotspot", "Accel mobile"], "partner_code": "PRT-1"})
    assert r["lead_source"] == "Channel partner" and r["current_internet"] == "Mobile hotspot" and r["has_gstin"] is True and r["current_provider"] == "Accel"
    assert scoring.raw_row(base)["current_provider"] is None
    assert scoring.raw_row({**base, "has_gstin": False, "channel": "whatsapp"})["lead_source"] == "WhatsApp campaign"
    hi, _ = scoring.score_lead({"raw_features": scoring.raw_row({**base, "has_gstin": True}), "id": "x"})
    lo, _ = scoring.score_lead({"raw_features": scoring.raw_row({**base, "has_gstin": False}), "id": "x"})
    assert hi > lo


# ------------------------------------------------------------------ funnel
def test_funnel_counts_follow_the_real_journey(empty):
    oid, r = run("K03")                                              # KYC approved
    sid = c.post("/advisor/sessions", json={}).json()["session_id"]
    c.post(f"/advisor/sessions/{sid}/messages", json={"text": "Kirana store in Jaipur, 2 staff, 1 shop, GST yes"})
    for _ in range(4):
        c.post(f"/admin/orders/{oid}/advance", headers=ADMIN)       # install steps -> ACTIVATED
    c.get(f"/orders/{oid}", params={"phone_last4": "3210", "track": "true"})
    f = compute()
    counts = {s["key"]: s["count"] for s in f["stages"]}
    assert counts == {"advisor_started": 1, "recommendation_shown": 1, "quote_accepted": 1, "order_placed": 1, "kyc_complete": 1, "activated": 1}
    k = f["kpis"]
    assert k["kyc_auto_approval_pct"] == 100.0 and k["kyc_decisions"] == 1 and k["status_checks_per_order"] == 1.0 and k["median_days_to_activate"] == 0
    assert f["seeded_events"] == 0 and f["baseline"]["status_checks_per_order"] == 3.0 and f["target"]["days_to_activate"] == 5.0


def test_funnel_endpoint_and_seed_flag(seeded):
    f = c.get("/backoffice/funnel", headers=AUTH).json()
    assert f["seeded_events"] > 0 and f["stages"][0]["count"] >= 30
    assert f["kpis"]["median_days_to_activate"] == 5 and f["kpis"]["orders"] == 3 and 0 < f["kpis"]["kyc_auto_approval_pct"] < 100


# ------------------------------------------------------------------ seed + reset
def test_seed_creates_three_demo_orders_in_different_states(seeded):
    demo = get_repo().get("meta", "demo")["orders"]
    states = sorted(get_repo().get("orders", d["id"])["state"] for d in demo)
    assert states == ["ACTIVATED", "KYC_ACTION_REQUIRED", "TECHNICIAN_ASSIGNED"]
    d = demo[1]
    r = c.get(f"/orders/{d['id']}", params={"phone_last4": d["last4"]})
    assert r.status_code == 200 and r.json()["tech"]


def test_admin_reset_needs_token_and_reseeds(seeded):
    assert c.post("/admin/reset").status_code == 401
    r = c.post("/admin/reset", headers=ADMIN).json()
    assert r["seeded"] and r["leads"] == 30 and len(r["demo_orders"]) == 3 and len(L()) == 31
