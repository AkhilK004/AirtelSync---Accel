from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.repo import get_repo

c = TestClient(app)
DOCS = settings.data_path / "kyc_documents"
SLOT_FILES = {"gst_certificate": "gst_certificate", "udyam_certificate": "udyam_certificate", "signatory_id": "signatory_id", "address_proof": "address_proof"}
REQ = ["kyc_verification", "service_delivery"]


def new_order() -> str:
    q = c.post("/quotes", json={"business_type": "Kirana store", "employees": 2, "locations": 1, "city_tier": 2, "gstin_status": "active"}).json()
    slot_date = (date.fromisoformat(settings.TODAY) + timedelta(days=2)).isoformat()
    r = c.post("/checkout", json=dict(quote_id=q["id"], phone="9876543210", otp="123456", business_name="Test Biz", address="12 Market Road, Jaipur",
                                      slot_date=slot_date, slot_window="morning", payment_mode="pay_on_activation", language="en"))
    return r.json()["order_id"]


def consent(oid, purposes=REQ, lang="en"):
    return c.post("/consents", json={"order_id": oid, "purposes": purposes, "language": lang})


def upload(oid, applicant, slot, lang="en"):
    f = DOCS / f"{applicant}_{SLOT_FILES[slot]}.png"
    return c.post(f"/kyc/{oid}/documents?lang={lang}", data={"slot": slot}, files={"file": (f.name, f.read_bytes(), "image/png")})


def run(applicant, lang="en", purposes=REQ):
    oid = new_order()
    assert consent(oid, purposes).status_code == 200
    for slot in SLOT_FILES:
        if (DOCS / f"{applicant}_{slot}.png").exists():
            assert upload(oid, applicant, slot, lang).status_code == 200
    return oid, c.post(f"/kyc/{oid}/evaluate?lang={lang}").json()


# ---------------------------------------------------------------- consent
def test_notice_in_three_languages_and_marketing_off_by_default():
    for lang in ("en", "hi", "mr"):
        n = c.get(f"/consents/notice?lang={lang}").json()
        assert n["version"] == "2026-07-v1" and n["language"] == lang and len(n["summary"]) == 5
        words = sum(len(s.split()) for s in n["summary"])
        assert words <= 130  # short notice (<= ~120 words, plus the section lead-ins)
        by = {p["id"]: p for p in n["purposes"]}
        assert by["marketing"]["default"] is False and by["marketing"]["required"] is False
        assert by["kyc_verification"]["required"] and by["service_delivery"]["required"]
        assert "partner_sharing" not in by
    assert "partner_sharing" in {p["id"] for p in c.get("/consents/notice?partner=true").json()["purposes"]}


def test_required_purposes_enforced_and_ledger_records_version_and_language():
    oid = new_order()
    r = consent(oid, ["marketing"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert consent(oid, ["kyc_verification", "bogus"]).json()["error"]["code"] == "PURPOSE_UNKNOWN"
    ok = consent(oid, REQ + ["marketing"], "hi").json()
    assert ok["notice_version"] == "2026-07-v1" and ok["language"] == "hi" and ok["principal_ref"] and "9876543210" not in str(ok)
    led = c.get(f"/consents/{oid}").json()
    assert led["effective"] == sorted(REQ + ["marketing"]) and len(led["ledger"]) == 1


def test_withdrawal_is_append_only_and_blocks_kyc():
    oid = new_order()
    g = consent(oid, REQ + ["marketing"]).json()
    w = c.post(f"/consents/{g['id']}/withdraw", json={"purposes": ["marketing"]}).json()
    assert w["kind"] == "withdraw" and w["ref_id"] == g["id"]
    led = c.get(f"/consents/{oid}").json()
    assert len(led["ledger"]) == 2 and "marketing" not in led["effective"] and led["ledger"][0]["kind"] == "grant"
    c.post(f"/consents/{g['id']}/withdraw", json={"purposes": ["kyc_verification"]})
    assert upload(oid, "K03", "gst_certificate").status_code == 403
    assert c.post(f"/consents/{g['id']}/withdraw", json={"purposes": ["partner_sharing"]}).status_code == 422
    try:
        get_repo().append("consents", g["id"], g)
        assert False, "append-only ledger must reject a duplicate id"
    except ValueError:
        pass


def test_kyc_endpoints_return_403_without_consent():
    oid = new_order()
    for fn in (lambda: c.post(f"/kyc/{oid}/lookup/gstin", json={"gstin": "32TTNXB7384T1ZW"}), lambda: upload(oid, "K03", "gst_certificate"),
               lambda: c.post(f"/kyc/{oid}/evaluate")):
        r = fn()
        assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_MISSING"
    assert c.post("/consents", json={"order_id": "nope", "purposes": REQ}).status_code == 404


# ---------------------------------------------------------------- lookups
def test_gstin_lookup_prefill_and_statuses():
    oid = new_order()
    consent(oid)
    ok = c.post(f"/kyc/{oid}/lookup/gstin", json={"gstin": "32ttn-xb7384t1zw"}).json()
    assert ok["record"]["legal_name"] == "Balaji Dental Care LLP" and ok["record"]["status"] == "Active" and "TTNXB7384T" not in ok["gstin"]
    assert all(x["status"] == "PASS" for x in ok["checks"])
    bad_sum = c.post(f"/kyc/{oid}/lookup/gstin", json={"gstin": "08YKZXS8189L1ZO"}).json()
    assert bad_sum["record"] is None and any(x["code"] == "GSTIN_CHECKSUM" and x["status"] == "FAIL" for x in bad_sum["checks"])
    cancelled = c.post(f"/kyc/{oid}/lookup/gstin", json={"gstin": "37IHKXV5167L1ZS"}).json()
    assert any(x["code"] == "GSTIN_STATUS" and x["status"] == "FAIL" for x in cancelled["checks"])
    assert c.post(f"/kyc/{oid}/lookup/gstin", json={"gstin": "XYZ"}).json()["checks"][0]["code"] == "GSTIN_FORMAT"


def test_udyam_lookup():
    oid = new_order()
    consent(oid)
    ok = c.post(f"/kyc/{oid}/lookup/udyam", json={"udyam_number": "udyam kl 00 3078801"}).json()
    assert ok["record"]["enterprise_name"] == "Balaji Dental Care LLP"
    assert c.post(f"/kyc/{oid}/lookup/udyam", json={"udyam_number": "UDYAM-KL-00-0000000"}).json()["record"] is None


# ---------------------------------------------------------------- end-to-end decisions through the API (specimens via fixture LLM)
def test_clean_applicant_approved_and_order_advances():
    oid, r = run("K03")
    assert r["decision"]["status"] == "APPROVED" and r["decision"]["reason_codes"] == []
    o = get_repo().get("orders", oid)
    assert o["state"] == "INSTALL_SCHEDULED" and "KYC_VERIFIED" in o["history"]  # verified, then install auto-scheduled for the chosen slot
    assert not get_repo().get("kyc_applications", oid)["review_files"]


def test_stale_bill_gives_fix_instruction_in_each_language():
    _, en = run("K11")
    fix = next(x for x in en["checks"] if x["code"] == "BILL_RECENCY")
    assert en["decision"]["status"] == "ACTION_REQUIRED" and "2026-04-16" in fix["fix"]
    _, hi = run("K11", "hi")
    h = next(x for x in hi["checks"] if x["code"] == "BILL_RECENCY")
    assert "2026-04-16" in h["fix"] and any("ऀ" <= ch <= "ॿ" for ch in h["message"])
    _, mr = run("K11", "mr")
    assert any("ऀ" <= ch <= "ॿ" for ch in next(x for x in mr["checks"] if x["code"] == "BILL_RECENCY")["fix"])


def test_blur_checksum_and_missing_udyam_number():
    _, k4 = run("K04")
    assert k4["decision"]["status"] == "ACTION_REQUIRED" and "IMG_QUALITY" in k4["decision"]["reason_codes"]
    _, k6 = run("K06")
    assert k6["decision"]["reason_codes"] == ["GSTIN_CHECKSUM"]
    oid, k1 = run("K01")
    assert k1["decision"]["status"] == "REJECTED" and get_repo().get("orders", oid)["state"] == "CANCELLED"


def test_tampered_certificate_goes_to_manual_review_with_image_retention_and_lead():
    oid, r = run("K07")
    assert r["decision"]["status"] == "MANUAL_REVIEW" and r["decision"]["review_hours"] == 24 and "24 hours" in r["decision"]["message"]
    app = get_repo().get("kyc_applications", oid)
    assert set(app["review_files"]) == {"gst_certificate", "udyam_certificate", "signatory_id", "address_proof"}
    assert get_repo().get("orders", oid)["state"] == "KYC_REVIEW"
    assert any(l.get("order_id") == oid and l["reason"] == "kyc_issue" for l in get_repo().list("leads"))
    assert any(a["action"] == "kyc_decided" and a["order_id"] == oid for a in get_repo().list("audit_log"))
    from app.kyc import review_store
    assert review_store.purge_expired(now=10**12) >= 4  # expired review images are deleted


def test_reupload_fixes_the_problem_and_invalidates_old_decision():
    oid, r = run("K11")
    assert r["decision"]["status"] == "ACTION_REQUIRED"
    assert upload(oid, "K03", "address_proof").status_code == 200  # a recent bill (different applicant's, only the date matters here)
    st = c.get(f"/kyc/{oid}").json()
    assert st["decision"] is None  # must re-evaluate after any new upload


def test_upload_validation_and_no_full_identifiers_in_responses():
    oid = new_order()
    consent(oid)
    assert c.post(f"/kyc/{oid}/documents", data={"slot": "gst_certificate"}, files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert c.post(f"/kyc/{oid}/documents", data={"slot": "gst_certificate"}, files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10), "image/png")}).status_code == 413
    assert c.post(f"/kyc/{oid}/documents", data={"slot": "passport"}, files={"file": ("a.png", b"\x89PNG", "image/png")}).status_code == 422
    r = upload(oid, "K03", "gst_certificate").json()
    assert "27XUIXG0767D1ZP" not in str(r) and r["summary"]["gstin"] == "27**********1ZP"
    assert "27XUIXG0767D1ZP" not in str(c.get(f"/kyc/{oid}").json())


def test_unknown_image_is_unreadable_not_a_crash():
    oid = new_order()
    consent(oid)
    import cv2
    import numpy as np
    img = np.random.default_rng(0).integers(0, 255, (800, 800), dtype=np.uint8)
    png = cv2.imencode(".png", img)[1].tobytes()
    r = c.post(f"/kyc/{oid}/documents", data={"slot": "gst_certificate"}, files={"file": ("x.png", png, "image/png")}).json()
    assert r["ok"] is False and r["checks"][0]["code"] == "IMG_QUALITY" and r["checks"][0]["fix"]


def test_eval_script_matches_expected_csv():
    import subprocess, sys, os
    env = dict(os.environ, LLM_PROVIDER="fake")
    out = subprocess.run([sys.executable, "../scripts/eval_kyc.py"], capture_output=True, text=True, env=env, cwd=Path(__file__).parents[1])
    assert out.returncode == 0, out.stdout + out.stderr
    assert "12/12 match" in out.stdout
