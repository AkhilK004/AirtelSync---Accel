from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

c = TestClient(app)
TOMORROW = (date.fromisoformat(settings.TODAY) + timedelta(days=2)).isoformat()


def _quote(lang="en"):
    p = {"business_type": "Kirana store", "employees": 2, "locations": 1, "city_tier": 2, "gstin_status": "active"}
    return c.post(f"/quotes?lang={lang}", json=p).json()


def body(qid, **kw):
    b = dict(quote_id=qid, phone="98765 43210", otp="123456", business_name="Ravi Kirana", address="12 Market Road, Jaipur",
             slot_date=TOMORROW, slot_window="morning", payment_mode="pay_on_activation", language="en")
    b.update(kw)
    return b


def test_quote_localised_hi_and_reasons():
    q = _quote("hi")
    assert q["bundle_title"] == "दुकान स्टार्टर" and q["lines"][0]["name"] == "बिज़ फाइबर 100" and q["lines"][0]["reason"]
    assert q["monthly_total_paise"] == _quote("en")["monthly_total_paise"]  # language never changes price
    assert any(n["key"] == "gst_extra" and "GST" in n["text"] for n in q["assumptions"])


def test_toggle_notice_is_localised():
    q = _quote("mr")
    r = c.post(f"/quotes/{q['id']}/toggle?lang=mr", json={"sku": "P19", "on": True}).json()
    assert r["quote"]["lines"][-1]["sku"] == "P19" and r["quote"]["lines"][-1]["name"] == "क्लाउड POS आणि बिलिंग"


def test_otp_and_order_flow():
    q = _quote()
    assert c.post("/checkout/otp", json={"phone": "9876543210"}).json()["sent"]
    assert c.post("/checkout/otp", json={"phone": "123"}).status_code == 422
    assert c.post("/checkout", json=body(q["id"], otp="000000")).json()["error"]["code"] == "OTP_INVALID"
    r = c.post("/checkout", json=body(q["id"]))
    assert r.status_code == 200 and r.json()["state"] == "PLACED"
    from app.repo import get_repo
    o = get_repo().get("orders", r.json()["order_id"])
    assert o["phone_last4"] == "3210" and "9876543210" not in str(o) and o["quote_snapshot"]["monthly_total_paise"] == q["monthly_total_paise"]


def test_checkout_validation():
    q = _quote()
    assert c.post("/checkout", json=body(q["id"], slot_date=settings.TODAY)).json()["error"]["code"] == "SLOT_DATE_INVALID"
    assert c.post("/checkout", json=body(q["id"], slot_window="night")).json()["error"]["code"] == "SLOT_INVALID"
    assert c.post("/checkout", json=body("nope")).json()["error"]["code"] == "QUOTE_NOT_FOUND"
    assert c.post("/checkout", json=body(q["id"], phone="12345")).status_code == 422
