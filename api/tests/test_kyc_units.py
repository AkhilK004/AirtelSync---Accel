import logging
from datetime import timedelta

import pytest

from app.data.loaders import get_data
from app.kyc import ids, quality, validators
from app.kyc.decision import decide
from app.logging import RedactionFilter, redact
from app.models.kyc import CheckResult

D = get_data()


# ---------------------------------------------------------------- ids (calibrated on the registries)
def test_all_registry_gstins_pass_format_and_checksum():
    assert all(ids.gstin_format_ok(g) and ids.gstin_checksum_ok(g) for g in D.gstin)


def test_all_registry_udyam_pass_format():
    assert all(ids.udyam_format_ok(u) for u in D.udyam)


def test_gstin_checksum_catches_single_char_errors():
    good = "08YKZXS5189L1ZO"
    assert ids.gstin_checksum_ok(good)
    assert not ids.gstin_checksum_ok("08YKZXS8189L1ZO")  # K06: digit changed
    assert not ids.gstin_checksum_ok("19E0GXH4115Y1ZL")  # zero instead of letter O


def test_gstin_state_codes_match_registry_100pct():
    assert all(ids.GST_STATE_CODES[g[:2]] == r.state for g, r in D.gstin.items())


def test_normalisers():
    assert ids.norm_gstin(" 32ttn-xb7384t1zw ") == "32TTNXB7384T1ZW"
    assert ids.norm_udyam("udyam kl 00 3078801") == "UDYAM-KL-00-3078801"


def test_verhoeff_and_masking():
    assert ids.verhoeff_ok("2363")  # known valid Verhoeff
    assert not ids.verhoeff_ok("2364")
    assert ids.mask_aadhaar("2345 6789 0123") == "XXXXXXXX0123"


def test_pan_rules():
    assert ids.pan_format_ok("ABCPE1234F") and not ids.pan_format_ok("ABCPE12345")
    assert ids.pan_entity_ok("ABCPE1234F") and ids.pan_entity_ok("ABCXE1234F")  # X accepted for synthetic data
    assert not ids.pan_entity_ok("ABCZE1234F")


# ---------------------------------------------------------------- quality
def test_quality_gate_on_specimens():
    def q(name):
        b = (D_PATH / name).read_bytes()
        return quality.assess(b, quality.sniff_mime(b))
    assert not q("K04_gst_certificate.png").ok and q("K04_gst_certificate.png").reason == "blurry"
    assert q("K02_gst_certificate.png").ok  # skewed but sharp
    assert q("K03_signatory_id.png").ok


def test_quality_small_and_undecodable_and_sniff():
    import cv2
    import numpy as np
    small = cv2.imencode(".png", np.full((200, 200), 255, np.uint8))[1].tobytes()
    assert quality.assess(small, "image/png").reason == "small"
    assert quality.assess(b"\x89PNG\r\n\x1a\nnotreally", "image/png").reason == "undecodable"
    assert quality.sniff_mime(b"%PDF-1.4") == "application/pdf" and quality.sniff_mime(b"GIF89a") is None


from app.config import settings  # noqa: E402

D_PATH = settings.data_path / "kyc_documents"


# ---------------------------------------------------------------- validators
def ex(**kw):
    base = {"confidence": 0.95}
    base.update(kw)
    return base


def codes(cs, status="FAIL"):
    return {c.code for c in cs if c.status == status}


def test_bill_recency_boundary():
    today = validators.today()
    ok = validators.doc_checks("address_proof", ex(doc_type_detected="address_proof", bill_date=(today - timedelta(days=90)).isoformat()), None)
    old = validators.doc_checks("address_proof", ex(doc_type_detected="address_proof", bill_date=(today - timedelta(days=91)).isoformat()), None)
    assert "BILL_RECENCY" not in codes(ok) and "BILL_RECENCY" in codes(old)
    f = next(c for c in old if c.code == "BILL_RECENCY")
    assert f.fix_key == "newer_bill" and f.params["min_date"] == (today - timedelta(days=90)).isoformat()


def test_future_dates_fail():
    fut = (validators.today() + timedelta(days=3)).isoformat()
    assert "DATE_LOGIC" in codes(validators.doc_checks("address_proof", ex(doc_type_detected="address_proof", bill_date=fut), None))
    assert "DATE_LOGIC" in codes(validators.doc_checks("gst_certificate", ex(doc_type_detected="gst_certificate", gstin="07CPCXN0398P1ZT", registration_date=fut), None))


def test_id_expiry_and_aadhaar():
    exp = validators.doc_checks("signatory_id", ex(doc_type_detected="signatory_id", id_number="SYN-ID-123456", expiry_date="2026-07-14"), None)
    assert "ID_EXPIRY" in codes(exp)
    ok = validators.doc_checks("signatory_id", ex(doc_type_detected="signatory_id", id_kind="aadhaar", verhoeff_ok=True, expiry_date=None), None)
    bad = validators.doc_checks("signatory_id", ex(doc_type_detected="signatory_id", id_kind="aadhaar", verhoeff_ok=False), None)
    assert "ID_FORMAT" not in codes(ok) and "ID_FORMAT" in codes(bad)


def test_wrong_document_and_low_confidence():
    wrong = validators.doc_checks("gst_certificate", ex(doc_type_detected="address_proof"), None)
    assert "DOC_TYPE" in codes(wrong) and wrong[-1].fix_key == "reupload_right_doc"
    assert codes(validators.doc_checks("gst_certificate", {"confidence": 0.2}, None)) == {"IMG_QUALITY"}


def test_name_normalisation_and_thresholds():
    assert validators.norm_name("M/s Ganesh Woodcraft Pvt. Ltd.") == "ganesh woodcraft"
    assert validators.name_score("Ganesh Woodcraft", "GANESH  WOODCRAFT PVT LTD") >= 90
    assert validators.name_score("Shri Physio Clinic", "Neelgiri Physio Clinic") < 90
    assert validators.split_legal("Neha Kaur (Prop. Vindhya Tours & Travels)") == ("Neha Kaur", "Vindhya Tours & Travels")
    assert validators.split_legal("Balaji Realty LLP") == (None, "Balaji Realty LLP")


def test_signatory_mismatch_for_proprietorship_only():
    gst = ex(doc_type_detected="gst_certificate", gstin="32TTNXB7384T1ZW", legal_name="Neha Kaur (Prop. Vindhya Tours & Travels)",
             trade_name="Vindhya Tours & Travels", address=None, registration_date=None)
    ident = ex(name="Someone Else", business_name="Vindhya Tours & Travels")
    cs = validators.cross_checks("gstin", {"gst_certificate": gst, "signatory_id": ident}, set(), None, None, {}, {})
    assert "SIGNATORY_MATCH" in codes(cs)


def test_declared_gstin_mismatch_and_missing_docs():
    gst = ex(doc_type_detected="gst_certificate", gstin="32TTNXB7384T1ZW")
    cs = validators.cross_checks("gstin", {"gst_certificate": gst}, set(), "27XUIXG0767D1ZP", None, D.gstin, D.udyam)
    assert {"GSTIN_DECLARED", "DOC_MISSING"} <= codes(cs)


# ---------------------------------------------------------------- decision
def c(code, status, fix=None):
    return CheckResult(code=code, status=status, message_key="x", fix_key=fix)


def test_decision_rules():
    assert decide([c("A", "PASS")]).status == "APPROVED"
    assert decide([c("GSTIN_STATUS", "FAIL"), c("IMG_QUALITY", "FAIL", "reupload_clear")]).status == "REJECTED"  # rejection wins
    assert decide([c("IMG_QUALITY", "FAIL", "reupload_clear"), c("CERT_VS_REGISTRY", "FAIL")]).status == "ACTION_REQUIRED"  # fix first
    assert decide([c("CERT_VS_REGISTRY", "FAIL")]).status == "MANUAL_REVIEW"
    assert decide([c("A", "WARN")]).status == "APPROVED"
    d = decide([c("A", "WARN"), c("B", "WARN")])
    assert d.status == "MANUAL_REVIEW" and d.review_hours == 24


# ---------------------------------------------------------------- logging redaction
def test_redaction():
    s = redact("call 9876543210 gstin 32TTNXB7384T1ZW pan ABCPE1234F aadhaar 2345 6789 0123 mail a.b@x.com")
    assert "9876543210" not in s and "32TTNXB7384T1ZW" not in s and "ABCPE1234F" not in s and "2345 6789 0123" not in s and "a.b@x.com" not in s
    assert "32**********1ZW" in s


def test_redaction_filter_on_log_record():
    rec = logging.LogRecord("kyc", logging.INFO, "f", 1, "phone %s", ("9876543210",), None)
    RedactionFilter().filter(rec)
    assert "9876543210" not in rec.getMessage() and "[phone]" in rec.getMessage()


@pytest.mark.parametrize("applicant", ["K01", "K06", "K11"])
def test_fixture_covers_all_images(applicant):
    import hashlib
    from app.llm.fake import _fixture
    for f in D.kyc[applicant]:
        assert hashlib.sha256(open(f.path, "rb").read()).hexdigest() in _fixture()


# ---------------------------------------------------------------- OCR repair (found in the first live Gemini run)
def test_repair_gstin_fixes_confusables_only_when_checksum_passes():
    assert ids.repair_gstin("19E0GXH4115Y1ZL") == "19EOGXH4115Y1ZL"      # K02: letter O read as zero
    assert ids.repair_gstin("24X0RXG9365M1Z3") == "24XORXG9365M1Z3"      # K08
    assert ids.repair_gstin("27PZSXS1936O1ZH") == "27PZSXS1936O1ZH"      # already valid: untouched
    assert ids.repair_gstin("08YKZXS8189L1Z0") == "08YKZXS8189L1Z0"      # K06: a genuinely wrong digit is NOT repaired
    assert ids.repair_gstin("08YKZXS8189L1ZO") == "08YKZXS8189L1ZO"
    assert ids.repair_gstin("abc") == "ABC" and ids.repair_gstin(None) is None


def test_wrapped_pincode_fix():
    assert ids.fix_wrapped_pincode("Shop/Unit 38, Civil Lines, Kochi, Kerala - 75 2083") == "Shop/Unit 38, Civil Lines, Kochi, Kerala - 752083"
    assert ids.fix_wrapped_pincode("Shop/Unit 38, Kochi, Kerala - 752083") == "Shop/Unit 38, Kochi, Kerala - 752083"
    assert ids.fix_wrapped_pincode("Plot 12 45, Kochi") == "Plot 12 45, Kochi"     # not a 6-digit split
    assert ids.fix_wrapped_pincode(None) is None


def test_extract_normalises_model_output(monkeypatch):
    from app.kyc import extract
    from app.llm import get_llm
    from app.models.kyc import GstCertExtract
    raw = GstCertExtract(doc_type_detected="gst_certificate", gstin="19E0GXH4115Y1ZL", address="Kolkata, West Bengal - 34 7550", confidence=0.9)
    monkeypatch.setattr(get_llm(), "extract", lambda *a, **k: raw)
    out = extract.extract_document("gst_certificate", b"x", "image/png")
    assert out.gstin == "19EOGXH4115Y1ZL" and out.address.endswith("347550")
