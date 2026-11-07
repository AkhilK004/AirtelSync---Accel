"""A66: advisor-era engagement signals (counts only) and the future training table."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.leads import engagement
from app.main import app
from app.repo import get_repo

c = TestClient(app)
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{settings.BACKOFFICE_USER}:{settings.BACKOFFICE_PASSWORD}".encode()).decode()}


@pytest.fixture(autouse=True)
def clean():
    get_repo().clear()
    yield
    get_repo().clear()


def journey(text="Pharmacy in Lucknow, 3 staff, 1 shop, GST yes, budget Rs 500"):
    sid = c.post("/advisor/sessions", json={}).json()["session_id"]
    c.post(f"/advisor/sessions/{sid}/messages", json={"text": text})
    return sid, c.get(f"/advisor/sessions/{sid}").json()["quote_id"]


def test_quote_events_are_logged_and_counted():
    sid, qid = journey()
    assert qid
    c.get(f"/quotes/{qid}")                                  # refetch: not a view
    assert c.get(f"/quotes/{qid}", params={"view": "true"}).status_code == 200
    c.get(f"/quotes/{qid}", params={"view": "true"})
    sku = next(a["sku"] for a in c.get(f"/quotes/{qid}").json()["addons"])
    c.post(f"/quotes/{qid}/toggle", json={"sku": sku, "on": True})
    c.post(f"/quotes/{qid}/toggle", json={"sku": sku, "on": False})
    assert c.post(f"/quotes/{qid}/shared").status_code == 204
    assert c.post("/quotes/nope/shared").status_code == 404
    e = c.get("/backoffice/engagement", headers=AUTH).json()["rows"][0]["engagement"]
    assert e["quote_views"] == 2 and e["addon_toggles"] == 2 and e["quote_shared"] == 1
    assert e["advisor_messages"] >= 1 and e["budget_stated"] is True and e["budget_gap_inr"] > 0   # Rs 500 is below the cheapest bundle
    assert set(e) == set(engagement.ENGAGEMENT_FEATURES)
    assert all(isinstance(v, (int, bool)) for v in e.values())                                      # counts only


def test_no_budget_means_no_gap():
    journey("Kirana store in Jaipur, 2 staff, 1 shop, GST yes")
    e = c.get("/backoffice/engagement", headers=AUTH).json()["rows"][0]["engagement"]
    assert e["budget_stated"] is False and e["budget_gap_inr"] == 0 and e["quote_views"] == 0


def test_engagement_table_requires_auth_and_reports_readiness():
    assert c.get("/backoffice/engagement").status_code == 401
    journey()
    r = c.get("/backoffice/engagement", headers=AUTH).json()
    row = r["rows"][0]
    assert row["reached_quote"] and not row["ordered"] and not row["activated"]
    assert {"segment", "city_tier", "lead_source", "has_gstin", "employee_count", "num_sites"} <= set(row["inputs"])
    assert r["readiness"]["journeys"] == 1 and r["readiness"]["ready"] is False
    assert engagement.readiness([{"activated": True}] * 30 + [{"activated": False}] * 270)["ready"] is True
    assert engagement.readiness([{"activated": True}] * 29 + [{"activated": False}] * 271)["ready"] is False


def test_lead_detail_carries_engagement_and_seed_leads_do_not():
    sid, qid = journey()
    c.get(f"/quotes/{qid}", params={"view": "true"})
    lid = c.post(f"/advisor/sessions/{sid}/handoff", json={"phone": "9876543210"}).json()["lead_id"]
    d = c.get(f"/backoffice/leads/{lid}", headers=AUTH).json()
    assert d["engagement"]["quote_views"] == 1 and d["engagement"]["handoff_requested"] >= 1
    from app.seed import seed_demo
    get_repo().clear()
    seed_demo(reset=True)
    seeded = [l for l in c.get("/backoffice/leads", headers=AUTH).json()["leads"] if not l["order_id"]][0]
    assert c.get(f"/backoffice/leads/{seeded['id']}", headers=AUTH).json()["engagement"] is None
