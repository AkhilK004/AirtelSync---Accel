"""KYC check against a DEPLOYED API over HTTP. Creates one real test order per applicant (business name 'KYC live check'), so use few applicants on a demo environment:
manual-review cases also write a lead and store images in the review bucket.
Usage: cd api && python -m uv run python ../scripts/eval_kyc_http.py --base-url https://<api> K03 K11"""
import argparse, csv, sys
from datetime import date, timedelta
from pathlib import Path
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", required=True)
ap.add_argument("applicants", nargs="+")
ap.add_argument("--docs", default="../data/raw/kyc_documents")
ap.add_argument("--expected", default="../docs/kyc_expected.csv")
a = ap.parse_args()
expected = {r["applicant_id"]: r["expected_decision"] for r in csv.DictReader(open(a.expected, encoding="utf-8"))}
c = httpx.Client(base_url=a.base_url.rstrip("/"), timeout=120)
today = date.fromisoformat(c.get("/meta").json()["today"])
bad = 0
for ap_id in a.applicants:
    q = c.post("/quotes", json={"business_type": "Kirana store", "employees": 2, "locations": 1, "city_tier": 2, "gstin_status": "active"}).json()
    o = c.post("/checkout", json=dict(quote_id=q["id"], phone="9876543210", otp="123456", business_name="KYC live check", address="12 Market Road, Jaipur",
                                      slot_date=(today + timedelta(days=2)).isoformat(), slot_window="morning", payment_mode="pay_on_activation", language="en")).json()
    oid = o["order_id"]
    r = c.post("/consents", json={"order_id": oid, "purposes": ["kyc_verification", "service_delivery"], "language": "en"})
    assert r.status_code == 200, r.text
    for slot in ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof"):
        f = Path(a.docs) / f"{ap_id}_{slot}.png"
        if f.exists():
            u = c.post(f"/kyc/{oid}/documents", data={"slot": slot}, files={"file": (f.name, f.read_bytes(), "image/png")})
            assert u.status_code == 200, (slot, u.text[:200])
    ev = c.post(f"/kyc/{oid}/evaluate").json()
    dec = ev["decision"]["status"]
    codes = sorted({k["code"] for k in ev["checks"] if k["status"] != "PASS"})
    ok = dec == expected.get(ap_id)
    bad += not ok
    print(f"{ap_id}  expected {expected.get(ap_id):16s} got {dec:16s} {'|'.join(codes) or '-':32s} {'OK' if ok else 'MISMATCH'}")
sys.exit(1 if bad else 0)
