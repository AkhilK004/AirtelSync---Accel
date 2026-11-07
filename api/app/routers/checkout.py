"""Mock checkout: OTP + order placement. The order state machine and tracker arrive in Phase 6."""
from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.advisor.models import now_iso
from app.analytics.events import log_event
from app.config import MAX_SLOT_DAYS_AHEAD, MOCK_OTP, PAYMENT_MODES, SLOT_WINDOWS, settings
from app.engine.pricing import build_quote, new_id
from app.errors import ApiError
from app.models.engine import QuoteState
from app.repo import get_repo

router = APIRouter(prefix="/checkout", tags=["checkout"])
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
SALT = "udyam-demo-salt"  # production: per-environment secret


class OtpBody(BaseModel):
    phone: str


class CheckoutBody(BaseModel):
    quote_id: str
    phone: str
    otp: str
    business_name: str = Field(..., min_length=2, max_length=120)
    address: str = Field(..., min_length=8, max_length=300)
    pincode: str | None = Field(None, pattern=r"^\d{6}$")
    slot_date: date
    slot_window: str
    payment_mode: str = "pay_on_activation"
    language: str = "en"

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = re.sub(r"[\s\-]", "", v).removeprefix("+91")
        if not PHONE_RE.match(v):
            raise ValueError("invalid phone")
        return v


def principal_ref(phone: str) -> str:
    return hashlib.sha256((phone + SALT).encode()).hexdigest()


@router.post("/otp")
def send_otp(body: OtpBody):
    phone = re.sub(r"[\s\-]", "", body.phone).removeprefix("+91")
    if not PHONE_RE.match(phone):
        raise ApiError(422, "PHONE_INVALID", "checkout.phone_invalid")
    return {"sent": True, "demo_hint": "Use 123456 (demo)" if settings.APP_ENV != "prod" else None}


@router.post("")
def place_order(body: CheckoutBody):
    if body.otp != MOCK_OTP:
        raise ApiError(400, "OTP_INVALID", "checkout.otp_invalid")
    if body.slot_window not in SLOT_WINDOWS:
        raise ApiError(422, "SLOT_INVALID", "checkout.slot_invalid")
    if body.payment_mode not in PAYMENT_MODES:
        raise ApiError(422, "PAYMENT_INVALID", "checkout.payment_invalid")
    today = date.fromisoformat(settings.TODAY)
    if not (today + timedelta(days=1) <= body.slot_date <= today + timedelta(days=MAX_SLOT_DAYS_AHEAD)):
        raise ApiError(422, "SLOT_DATE_INVALID", "checkout.slot_date_invalid", {"max_days": MAX_SLOT_DAYS_AHEAD})
    repo = get_repo()
    d = repo.get("quotes", body.quote_id)
    if not d:
        raise ApiError(404, "QUOTE_NOT_FOUND", "quote.not_found")
    quote = build_quote(QuoteState.model_validate(d), body.language if body.language in ("en", "hi", "mr") else "en")
    oid = new_id()
    order = {
        "id": oid, "created_at": now_iso(), "quote_id": body.quote_id, "state": "PLACED", "language": body.language,
        "principal_ref": principal_ref(body.phone), "phone_last4": body.phone[-4:],
        "business_name": body.business_name.strip(), "address": body.address.strip(), "pincode": body.pincode,
        "slot": {"date": body.slot_date.isoformat(), "window": body.slot_window}, "payment_mode": body.payment_mode,
        "quote_snapshot": quote.model_dump(mode="json"),  # prices are frozen at order time
    }
    repo.put("orders", oid, order)
    log_event("quote_accepted", body.quote_id, {"total_paise": quote.monthly_total_paise})
    log_event("checkout_completed", oid, {"payment_mode": body.payment_mode})
    return {"order_id": oid, "state": "PLACED", "monthly_total_display": quote.monthly_total_display}
