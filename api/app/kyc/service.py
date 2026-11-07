"""KYC orchestration: consent gate -> lookups -> uploads (in-memory processing) -> evaluation -> order state, review queue, audit."""
from __future__ import annotations

import logging
import time

from app.advisor.models import now_iso
from app.analytics.events import log_event
from app.consent.service import require_kyc_consent
from app.data.loaders import get_data
from app.engine.pricing import new_id
from app.errors import ApiError
from app.i18n import render_check, render_decision
from app.kyc import ids, quality, review_store, validators
from app.kyc.pipeline import evaluate as run_eval
from app.kyc.pipeline import process_document
from app.models.kyc import SLOTS, KycApplication
from app.orders import service as orders
from app.repo import get_repo

log = logging.getLogger("kyc")
_PENDING: dict[tuple[str, str], tuple[bytes, str, float]] = {}  # (order, slot) -> (bytes, mime, ts); process memory only
PENDING_TTL = 1800


def _order(order_id: str) -> dict:
    o = get_repo().get("orders", order_id)
    if not o:
        raise ApiError(404, "ORDER_NOT_FOUND", "order.not_found")
    return o


def _set_state(order: dict, state: str, **extra) -> None:
    orders.kyc_result(order, state, **extra)  # legal transitions only; ignored once the order left the KYC family


def load(order_id: str) -> KycApplication:
    d = get_repo().get("kyc_applications", order_id)
    return KycApplication.model_validate(d) if d else KycApplication(order_id=order_id)


def save(app: KycApplication) -> None:
    get_repo().put("kyc_applications", app.order_id, app.model_dump(mode="json"))


def _gate(order_id: str, lang: str) -> tuple[dict, KycApplication]:
    require_kyc_consent(order_id)
    o = _order(order_id)
    app = load(order_id)
    app.language = lang
    if o["state"] == "PLACED":
        _set_state(o, "KYC_PENDING")
    return o, app


def mask_gstin(g: str | None) -> str | None:
    return g[:2] + "*" * 10 + g[-3:] if g and len(g) == 15 else g


def set_path(order_id: str, path: str, lang: str) -> dict:
    _, app = _gate(order_id, lang)
    app.path = path  # type: ignore[assignment]
    save(app)
    return {"path": app.path, "required": validators.required_slots(app.path)}


def lookup_gstin(order_id: str, gstin: str, lang: str) -> dict:
    _, app = _gate(order_id, lang)
    g = ids.norm_gstin(gstin) or ""
    checks = []
    if not ids.gstin_format_ok(g):
        checks.append(validators.ck("GSTIN_FORMAT", "FAIL", "gstin_format_bad", {"gstin": g}, "correct_number"))
    elif not ids.gstin_checksum_ok(g):
        checks += [validators.ck("GSTIN_FORMAT", "PASS", "check_ok"), validators.ck("GSTIN_CHECKSUM", "FAIL", "gstin_checksum_bad", {"gstin": g}, "correct_number")]
    else:
        checks += [validators.ck("GSTIN_FORMAT", "PASS", "check_ok"), validators.ck("GSTIN_CHECKSUM", "PASS", "check_ok")]
    rec = None
    if all(c.status == "PASS" for c in checks):
        rec = get_data().gstin.get(g)
        if rec is None:
            checks.append(validators.ck("GSTIN_REGISTRY", "FAIL", "gstin_not_found", {"gstin": g}, "correct_number"))
        else:
            checks.append(validators.ck("GSTIN_REGISTRY", "PASS", "check_ok"))
            checks.append(validators.ck("GSTIN_STATUS", "PASS" if rec.status == "Active" else "FAIL", "check_ok" if rec.status == "Active" else "gstin_inactive", {"status": rec.status}))
            app.declared_gstin = g
            app.path = "gstin"
            save(app)
    return {"gstin": mask_gstin(g), "checks": [render_check(c, lang) for c in checks],
            "record": ({"legal_name": rec.legal_name, "trade_name": rec.trade_name, "address": rec.address, "state": rec.state, "status": rec.status,
                        "constitution": rec.constitution} if rec else None)}


def lookup_udyam(order_id: str, number: str, lang: str) -> dict:
    _, app = _gate(order_id, lang)
    u = ids.norm_udyam(number) or ""
    checks, rec = [], None
    if not ids.udyam_format_ok(u):
        checks.append(validators.ck("UDYAM_FORMAT", "FAIL", "udyam_bad", {"number": u}, "correct_number"))
    else:
        checks.append(validators.ck("UDYAM_FORMAT", "PASS", "check_ok"))
        rec = get_data().udyam.get(u)
        checks.append(validators.ck("UDYAM_REGISTRY", "PASS", "check_ok") if rec else validators.ck("UDYAM_REGISTRY", "FAIL", "udyam_not_found", {"number": u}, "correct_number"))
        if rec:
            app.declared_udyam = u
            if not app.declared_gstin:
                app.path = "udyam"
            save(app)
    return {"udyam_number": u, "checks": [render_check(c, lang) for c in checks],
            "record": ({"enterprise_name": rec.enterprise_name, "enterprise_type": rec.enterprise_type, "city": rec.city, "state": rec.state} if rec else None)}


def upload(order_id: str, slot: str, data: bytes, lang: str) -> dict:
    if slot not in SLOTS:
        raise ApiError(422, "SLOT_UNKNOWN", "kyc.slot_unknown")
    if len(data) > quality.MAX_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "kyc.file_too_large", {"max_mb": 5})
    mime = quality.sniff_mime(data)  # trust content, not the client's Content-Type
    if mime is None:
        raise ApiError(415, "FILE_TYPE", "kyc.file_type")
    _, app = _gate(order_id, lang)
    ex, checks, q = process_document(slot, data, mime)
    app.docs[slot], app.doc_checks[slot] = ex, checks
    app.decision, app.checks = None, []  # any new upload invalidates the previous evaluation
    save(app)
    _PENDING[(order_id, slot)] = (data, mime, time.time())  # kept in memory only until evaluation; persisted only for manual review
    log_event("kyc_doc_uploaded", order_id, {"slot": slot, "ok": all(c.status != "FAIL" for c in checks)})
    summary = {k: (mask_gstin(v) if k == "gstin" else v) for k, v in ex.items()
               if k in ("legal_name", "trade_name", "gstin", "udyam_number", "enterprise_name", "name", "business_name", "bill_date", "expiry_date", "address") and v}
    return {"slot": slot, "checks": [render_check(c, lang) for c in checks], "summary": summary,
            "ok": all(c.status != "FAIL" for c in checks), "sharpness": round(q.sharpness, 1)}


def _purge_pending(order_id: str, keep: bool, app: KycApplication) -> None:
    now = time.time()
    for key in [k for k, v in _PENDING.items() if k[0] == order_id or now - v[2] > PENDING_TTL]:
        data, mime, _ts = _PENDING.pop(key)
        if keep and key[0] == order_id:
            app.review_files[key[1]] = review_store.put(order_id, key[1], data, mime)


def evaluate(order_id: str, lang: str) -> dict:
    o, app = _gate(order_id, lang)
    checks, dec = run_eval(app)
    app.checks, app.decision = checks, dec
    _purge_pending(order_id, keep=dec.status == "MANUAL_REVIEW", app=app)
    save(app)
    state = {"APPROVED": "KYC_VERIFIED", "ACTION_REQUIRED": "KYC_ACTION_REQUIRED", "MANUAL_REVIEW": "KYC_REVIEW", "REJECTED": "CANCELLED"}[dec.status]
    _set_state(o, state, **({"cancel_reason": "kyc_rejected"} if dec.status == "REJECTED" else {}))
    if dec.status in ("MANUAL_REVIEW", "REJECTED"):
        _kyc_lead(o, dec.status, dec.reason_codes)
    get_repo().put("audit_log", new_id(), {"ts": now_iso(), "actor": "system", "action": "kyc_decided", "order_id": order_id,
                                           "decision": dec.status, "codes": dec.reason_codes})
    log_event("kyc_decided", order_id, {"decision": dec.status, "codes": dec.reason_codes})
    log.info("kyc_decided order=%s decision=%s codes=%s", order_id[-6:], dec.status, ",".join(dec.reason_codes))
    return view(order_id, lang)


def _kyc_lead(order: dict, status: str, codes: list[str]) -> None:
    lid = new_id()
    get_repo().put("leads", lid, {
        "id": lid, "created_at": now_iso(), "session_id": None, "profile": {"business_name": order.get("business_name")}, "segment": None,
        "stage_reached": "kyc", "reason": "kyc_issue", "kyc_status": status, "kyc_codes": codes, "quote_id": order.get("quote_id"),
        "order_id": order["id"], "score": None, "score_reasons": [], "route_to": "telesales", "partner_code": None, "status": "new",
    })


def view(order_id: str, lang: str) -> dict:
    _order(order_id)
    app = load(order_id)
    dec = app.decision
    return {"order_id": order_id, "path": app.path, "required": validators.required_slots(app.path), "uploaded": sorted(app.docs),
            "declared_gstin": mask_gstin(app.declared_gstin), "declared_udyam": app.declared_udyam,
            "checks": [render_check(c, lang) for c in app.checks] if dec else
                      [render_check(c, lang) for cs in app.doc_checks.values() for c in cs],
            "decision": ({"status": dec.status, "message": render_decision(dec.status, lang, dec.review_hours), "reason_codes": dec.reason_codes,
                          "review_hours": dec.review_hours} if dec else None)}
