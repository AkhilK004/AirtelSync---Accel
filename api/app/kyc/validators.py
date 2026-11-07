"""KYC validators: pure functions, each returns CheckResult(s). Thresholds are config / calibrated (docs/assumptions.md)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from dateutil import parser as dparser
from rapidfuzz import fuzz

from app.config import settings
from app.kyc import ids
from app.kyc.quality import Quality
from app.models.domain import GstinRecord, UdyamRecord
from app.models.kyc import CheckResult

CERT_ADDRESS_MIN = 90
CERT_NAME_MIN = 95
SIGNATORY_MIN = 85
ADDRESS_MIN = 70
LOW_CONFIDENCE = 0.5
_STOP = {"m/s", "ms", "pvt", "ltd", "private", "limited", "llp", "co", "company"}


def ck(code: str, status: str, key: str, params: dict | None = None, fix: str | None = None, slot: str | None = None) -> CheckResult:
    return CheckResult(code=code, status=status, message_key=key, params=params or {}, fix_key=fix, slot=slot)  # type: ignore[arg-type]


def today() -> date:
    return date.fromisoformat(settings.TODAY)


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return dparser.parse(s, dayfirst=True).date() if not re.match(r"^\d{4}-\d{2}-\d{2}$", s.strip()) else date.fromisoformat(s.strip())
    except (ValueError, OverflowError):
        return None


def norm_name(s: str | None) -> str:
    t = re.sub(r"[^\w\s]", " ", (s or "").lower().replace("m/s", " "))
    return " ".join(w for w in t.split() if w not in _STOP)


def split_legal(legal: str | None) -> tuple[str | None, str]:
    """'Neha Kaur (Prop. Vindhya Tours & Travels)' -> ('Neha Kaur', 'Vindhya Tours & Travels'); entities -> (None, name)."""
    m = re.match(r"^(.*?)\s*\(\s*Prop\.?\s*(.*?)\s*\)\s*$", legal or "", re.I)
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, (legal or "").strip())


def name_score(a: str | None, b: str | None) -> float:
    return float(fuzz.token_sort_ratio(norm_name(a), norm_name(b)))


def pincode(addr: str | None) -> str | None:
    m = re.search(r"(\d{6})\s*$", addr or "")
    return m.group(1) if m else None


def _date_logic(code_slot: str, label: str, d: date | None, raw: str | None) -> list[CheckResult]:
    if raw and d is None:
        return [ck("DATE_LOGIC", "FAIL", "date_unreadable", {"field": label}, "reupload_clear", code_slot)]
    if d and d > today():
        return [ck("DATE_LOGIC", "FAIL", "date_future", {"field": label, "date": d.isoformat()}, "correct_number", code_slot)]
    return []


# --------------------------------------------------------------------------- per-document checks
def doc_checks(slot: str, ex: dict, quality: Quality | None) -> list[CheckResult]:
    out: list[CheckResult] = []
    if quality is not None and not quality.ok:
        key = {"blurry": "img_blurry", "small": "img_small", "undecodable": "img_unreadable"}[quality.reason or "undecodable"]
        return [ck("IMG_QUALITY", "FAIL", key, {"min_side": 600}, "reupload_clear", slot)]
    if ex.get("doc_type_detected") == "__service_error__":
        return [ck("IMG_QUALITY", "FAIL", "service_busy", {}, "try_again", slot)]
    if float(ex.get("confidence") or 0) < LOW_CONFIDENCE:
        return [ck("IMG_QUALITY", "FAIL", "img_unreadable", {}, "reupload_clear", slot)]
    out.append(ck("IMG_QUALITY", "PASS", "check_ok", {}, None, slot))
    detected = (ex.get("doc_type_detected") or "").strip()
    if detected and detected != slot:
        return out + [ck("DOC_TYPE", "FAIL", "doc_wrong", {"detected": detected, "expected": slot}, "reupload_right_doc", slot)]
    out.append(ck("DOC_TYPE", "PASS", "check_ok", {}, None, slot))

    if slot == "gst_certificate":
        g = ids.norm_gstin(ex.get("gstin"))
        if not ids.gstin_format_ok(g):
            out.append(ck("GSTIN_FORMAT", "FAIL", "gstin_format_bad", {"gstin": g or ""}, "correct_number", slot))
        else:
            out.append(ck("GSTIN_FORMAT", "PASS", "check_ok", {}, None, slot))
            if ids.gstin_checksum_ok(g):
                out.append(ck("GSTIN_CHECKSUM", "PASS", "check_ok", {}, None, slot))
            else:
                out.append(ck("GSTIN_CHECKSUM", "FAIL", "gstin_checksum_bad", {"gstin": g}, "correct_number", slot))
        d = parse_date(ex.get("registration_date"))
        out += _date_logic(slot, "registration_date", d, ex.get("registration_date"))
    elif slot == "udyam_certificate":
        u = ids.norm_udyam(ex.get("udyam_number"))
        if not u:
            out.append(ck("UDYAM_FORMAT", "FAIL", "udyam_missing", {}, "enter_udyam_number", slot))
        elif not ids.udyam_format_ok(u):
            out.append(ck("UDYAM_FORMAT", "FAIL", "udyam_bad", {"number": u}, "correct_number", slot))
        else:
            out.append(ck("UDYAM_FORMAT", "PASS", "check_ok", {}, None, slot))
        out += _date_logic(slot, "registration_date", parse_date(ex.get("registration_date")), ex.get("registration_date"))
    elif slot == "signatory_id":
        kind, num = ex.get("id_kind") or "other", ex.get("id_number")
        if kind == "pan":
            ok = ids.pan_format_ok(num)
            out.append(ck("ID_FORMAT", "PASS" if ok and ids.pan_entity_ok(num) else ("WARN" if ok else "FAIL"),
                          "check_ok" if ok and ids.pan_entity_ok(num) else ("pan_entity_odd" if ok else "id_format_bad"), {}, None if ok else "correct_number", slot))
        elif kind == "aadhaar":
            ok = bool(ex.get("verhoeff_ok"))
            out.append(ck("ID_FORMAT", "PASS" if ok else "FAIL", "check_ok" if ok else "id_format_bad", {}, None if ok else "correct_number", slot))
        elif kind == "other" and num and ids.SYN_ID_RE.match(num):
            out.append(ck("ID_FORMAT", "PASS", "check_ok", {}, None, slot))
        elif num:
            out.append(ck("ID_FORMAT", "WARN", "id_format_unchecked", {}, None, slot))  # DL / passport / voter: no registry to check against
        else:
            out.append(ck("ID_FORMAT", "FAIL", "id_format_bad", {}, "reupload_clear", slot))
        exp = parse_date(ex.get("expiry_date"))
        if exp and exp < today():
            out.append(ck("ID_EXPIRY", "FAIL", "id_expired", {"date": exp.isoformat()}, "valid_id", slot))
        elif exp:
            out.append(ck("ID_EXPIRY", "PASS", "check_ok", {}, None, slot))
        out += _date_logic(slot, "dob", parse_date(ex.get("dob")), ex.get("dob"))
    elif slot == "address_proof":
        d = parse_date(ex.get("bill_date"))
        if d is None:
            out.append(ck("BILL_RECENCY", "FAIL", "date_unreadable", {"field": "bill_date"}, "reupload_clear", slot))
        elif d > today():
            out.append(ck("DATE_LOGIC", "FAIL", "date_future", {"field": "bill_date", "date": d.isoformat()}, "newer_bill", slot))
        else:
            age = (today() - d).days
            if age > settings.BILL_MAX_AGE_DAYS:
                out.append(ck("BILL_RECENCY", "FAIL", "bill_old", {"date": d.isoformat(), "days": settings.BILL_MAX_AGE_DAYS,
                                                                    "min_date": (today() - timedelta(days=settings.BILL_MAX_AGE_DAYS)).isoformat()}, "newer_bill", slot))
            else:
                out.append(ck("BILL_RECENCY", "PASS", "check_ok", {}, None, slot))
    return out


# --------------------------------------------------------------------------- cross-document checks
def required_slots(path: str) -> list[str]:
    return {"gstin": ["gst_certificate", "signatory_id", "address_proof"], "udyam": ["udyam_certificate", "signatory_id", "address_proof"],
            "pan": ["signatory_id", "address_proof"]}[path]


def cross_checks(path: str, docs: dict[str, dict], failed_slots: set[str], declared_gstin: str | None, declared_udyam: str | None,
                 gstin_reg: dict[str, GstinRecord], udyam_reg: dict[str, UdyamRecord]) -> list[CheckResult]:
    out: list[CheckResult] = []
    for s in required_slots(path):
        if s not in docs:
            out.append(ck("DOC_MISSING", "FAIL", "doc_missing", {"slot": s}, "upload_doc", s))
    gst, udy, idc, bill = (docs.get(k) or {} for k in ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof"))
    gst_ok = "gst_certificate" in docs and "gst_certificate" not in failed_slots
    udy_ok = "udyam_certificate" in docs and "udyam_certificate" not in failed_slots

    # ---- GSTIN against the registry
    g = ids.norm_gstin(gst.get("gstin")) if gst_ok else None
    dg = ids.norm_gstin(declared_gstin)
    if g and dg and g != dg:
        out.append(ck("GSTIN_DECLARED", "FAIL", "gstin_declared_mismatch", {"declared": dg, "printed": g}, "correct_number", "gst_certificate"))
    key = g or (dg if ids.gstin_format_ok(dg) and ids.gstin_checksum_ok(dg or "") else None)
    rec: GstinRecord | None = None
    if key and ids.gstin_format_ok(key) and ids.gstin_checksum_ok(key):
        rec = gstin_reg.get(key)
        if rec is None:
            out.append(ck("GSTIN_REGISTRY", "FAIL", "gstin_not_found", {"gstin": key}, "correct_number", "gst_certificate"))
        else:
            out.append(ck("GSTIN_REGISTRY", "PASS", "check_ok", {}, None, "gst_certificate"))
            if rec.status == "Active":
                out.append(ck("GSTIN_STATUS", "PASS", "check_ok", {}, None, "gst_certificate"))
            else:
                out.append(ck("GSTIN_STATUS", "FAIL", "gstin_inactive", {"status": rec.status}, None, "gst_certificate"))
            exp_state = ids.GST_STATE_CODES.get(key[:2])
            if exp_state and exp_state.lower() != rec.state.lower():
                out.append(ck("GSTIN_STATE", "WARN", "gstin_state_mismatch", {"code": key[:2], "state": rec.state}, None, "gst_certificate"))
            else:
                out.append(ck("GSTIN_STATE", "PASS", "check_ok", {}, None, "gst_certificate"))

    # ---- printed certificate vs registry record (tampering signal)
    if rec is not None and gst_ok and gst.get("legal_name"):
        diffs = []
        if name_score(gst.get("legal_name"), rec.legal_name) < CERT_NAME_MIN:
            diffs.append("legal_name")
        if gst.get("trade_name") and name_score(gst.get("trade_name"), rec.trade_name) < CERT_NAME_MIN:
            diffs.append("trade_name")
        if gst.get("address") and fuzz.token_sort_ratio(norm_name(gst["address"]), norm_name(rec.address)) < CERT_ADDRESS_MIN:
            diffs.append("address")
        d = parse_date(gst.get("registration_date"))
        if d and d != rec.registration_date:
            diffs.append("registration_date")
        out.append(ck("CERT_VS_REGISTRY", "FAIL", "cert_mismatch", {"fields": ", ".join(diffs)}, None, "gst_certificate") if diffs
                   else ck("CERT_VS_REGISTRY", "PASS", "check_ok", {}, None, "gst_certificate"))

    # ---- Udyam
    u = ids.norm_udyam(udy.get("udyam_number")) if udy_ok else None
    if not u and declared_udyam:
        u = ids.norm_udyam(declared_udyam)
    urec = None
    if u and ids.udyam_format_ok(u):
        urec = udyam_reg.get(u)
        out.append(ck("UDYAM_REGISTRY", "PASS", "check_ok", {}, None, "udyam_certificate") if urec else
                   ck("UDYAM_REGISTRY", "FAIL", "udyam_not_found", {"number": u}, "correct_number", "udyam_certificate"))
    # UDYAM_CATEGORY is not enforced: enterprise type is uncorrelated with headcount in the data (docs/assumptions.md A31)

    # ---- names (all pairs among readable sources; worst pair decides)
    owner, gst_biz = split_legal(gst.get("legal_name") if gst_ok else (rec.legal_name if rec else None))
    names: list[tuple[str, str, str]] = []
    trade = (gst.get("trade_name") if gst_ok else None) or (rec.trade_name if rec else None)
    if gst_ok and gst_biz and trade:
        names.append(("legal_business", gst_biz, "trade_name"))
    refs = [("trade_name", trade)] if trade else []
    if udy_ok and udy.get("enterprise_name"):
        refs.append(("udyam", udy["enterprise_name"]))
    if "signatory_id" in docs and idc.get("business_name"):
        refs.append(("id_business", idc["business_name"]))
    if "address_proof" in docs and "address_proof" not in failed_slots and bill.get("customer_name"):
        refs.append(("bill", bill["customer_name"]))
    pairs = []
    base_name = gst_biz or (refs[0][1] if refs else None)
    for label, val in refs:
        if base_name and val and (label, val) != ("trade_name", trade):
            pairs.append((label, name_score(base_name, val), base_name, val))
    if gst_ok and gst_biz and trade:
        pairs.append(("legal_vs_trade", name_score(gst_biz, trade), gst_biz, trade))
    if pairs:
        worst = min(pairs, key=lambda p: p[1])
        st = "PASS" if worst[1] >= settings.NAME_MATCH_PASS else ("WARN" if worst[1] >= settings.NAME_MATCH_WARN else "FAIL")
        out.append(ck("NAME_MATCH", st, "check_ok" if st == "PASS" else "name_mismatch", {"a": worst[2], "b": worst[3], "score": int(worst[1])}, None, None))

    # ---- signatory vs owner
    if "signatory_id" in docs and idc.get("name") and gst_ok:
        if owner:
            sc = name_score(owner, idc["name"])
            out.append(ck("SIGNATORY_MATCH", "PASS", "check_ok", {}, None, "signatory_id") if sc >= SIGNATORY_MIN
                       else ck("SIGNATORY_MATCH", "FAIL", "signatory_mismatch", {"id_name": idc["name"], "owner": owner}, None, "signatory_id"))
        else:  # companies / LLPs: the registry holds no individual names (docs/assumptions.md A30)
            out.append(ck("SIGNATORY_MATCH", "PASS", "signatory_unverifiable", {}, None, "signatory_id"))

    # ---- address: bill vs registered (or certificate) address
    reg_addr = rec.address if rec else (gst.get("address") if gst_ok else None)
    if "address_proof" in docs and "address_proof" not in failed_slots and bill.get("address") and reg_addr:
        same_pin = pincode(bill["address"]) == pincode(reg_addr)
        sc = fuzz.token_sort_ratio(norm_name(bill["address"]), norm_name(reg_addr))
        out.append(ck("ADDRESS_MATCH", "PASS", "check_ok", {}, None, "address_proof") if same_pin and sc >= ADDRESS_MIN
                   else ck("ADDRESS_MATCH", "WARN", "address_mismatch", {}, None, "address_proof"))
    return out
