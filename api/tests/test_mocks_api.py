from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def test_gstin_lookup_ok_and_normalised():
    r = c.get("/mock/gstin/32ttnxb7384t1zw")
    assert r.status_code == 200 and r.json()["legal_name"] == "Balaji Dental Care LLP" and r.json()["status"] == "Active"
    assert c.get("/mock/gstin/32TTN-XB7384T1ZW").status_code == 200


def test_gstin_404_error_format():
    r = c.get("/mock/gstin/00AAAAA0000A1Z5")
    assert r.status_code == 404 and r.json()["error"]["code"] == "GSTIN_NOT_FOUND"


def test_udyam_lookup_variants():
    for v in ("UDYAM-KL-00-3078801", "udyam kl 00 3078801", "UDYAMKL003078801"):
        r = c.get(f"/mock/udyam/{v}")
        assert r.status_code == 200 and r.json()["enterprise_name"] == "Balaji Dental Care LLP", v
    assert c.get("/mock/udyam/UDYAM-KL-00-0000000").status_code == 404


def test_quote_api_flow():
    p = {"business_type": "Restaurant chain", "employees": 40, "locations": 4, "city_tier": 1, "gstin_status": "active"}
    q = c.post("/quotes", json=p).json()
    assert q["segment"] == "multi_site" and q["monthly_total_paise"] == 938800 + 168984
    r = c.post(f"/quotes/{q['id']}/toggle", json={"sku": "P23", "on": True})
    assert r.status_code == 200 and r.json()["quote"]["monthly_total_paise"] > q["monthly_total_paise"]
    assert c.get(f"/quotes/{q['id']}").json()["monthly_total_paise"] == r.json()["quote"]["monthly_total_paise"]
    bad = c.post(f"/quotes/{q['id']}/toggle", json={"sku": "P01", "on": False})
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "REQUIRED_LINE"
    assert c.get("/quotes/nope").status_code == 404
