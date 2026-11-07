from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GstCertExtract(BaseModel):
    doc_type_detected: str = ""
    gstin: str | None = None
    legal_name: str | None = None
    trade_name: str | None = None
    address: str | None = None
    state: str | None = None
    registration_date: str | None = None
    constitution: str | None = None
    signatory_names: list[str] = []
    confidence: float = 0.0


class UdyamCertExtract(BaseModel):
    doc_type_detected: str = ""
    udyam_number: str | None = None
    enterprise_name: str | None = None
    enterprise_type: str | None = None
    owner_name: str | None = None
    address: str | None = None
    registration_date: str | None = None
    pan: str | None = None
    gstin: str | None = None
    confidence: float = 0.0


class IdExtract(BaseModel):
    doc_type_detected: str = ""
    id_kind: Literal["pan", "aadhaar", "driving_licence", "passport", "voter_id", "other"] = "other"
    id_number: str | None = None
    name: str | None = None
    dob: str | None = None
    expiry_date: str | None = None
    designation: str | None = None      # authorised-signatory cards
    business_name: str | None = None    # "For business" on the card
    verhoeff_ok: bool | None = None     # Aadhaar only; the number itself is never kept
    confidence: float = 0.0


class BillExtract(BaseModel):
    doc_type_detected: str = ""
    provider: str | None = None
    customer_name: str | None = None
    address: str | None = None
    bill_date: str | None = None
    consumer_no: str | None = None
    confidence: float = 0.0


SLOT_SCHEMAS: dict[str, type[BaseModel]] = {
    "gst_certificate": GstCertExtract, "udyam_certificate": UdyamCertExtract, "signatory_id": IdExtract, "address_proof": BillExtract,
}
SLOTS = tuple(SLOT_SCHEMAS)


class CheckResult(BaseModel):
    code: str
    status: Literal["PASS", "WARN", "FAIL"]
    message_key: str
    params: dict = {}
    fix_key: str | None = None
    slot: str | None = None


class Decision(BaseModel):
    status: Literal["APPROVED", "MANUAL_REVIEW", "ACTION_REQUIRED", "REJECTED"]
    reason_codes: list[str] = []
    review_hours: int | None = None


class KycApplication(BaseModel):
    order_id: str
    path: Literal["gstin", "udyam", "pan"] = "gstin"
    declared_gstin: str | None = None
    declared_udyam: str | None = None
    docs: dict[str, dict] = {}                 # slot -> masked extract
    doc_checks: dict[str, list[CheckResult]] = {}
    checks: list[CheckResult] = []             # last evaluation (per-doc + cross-doc)
    decision: Decision | None = None
    language: str = "en"
    review_files: dict[str, str] = {}          # slot -> review-store key (manual review only)
