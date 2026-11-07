"""extraction -> per-document checks -> cross-document checks -> decision. Shared by the API and scripts/eval_kyc.py."""
from __future__ import annotations

from app.data.loaders import get_data
from app.kyc import quality, validators
from app.kyc.decision import decide
from app.kyc.extract import extract_document
from app.models.kyc import CheckResult, Decision, KycApplication


def process_document(slot: str, data: bytes, mime: str) -> tuple[dict, list[CheckResult], quality.Quality]:
    q = quality.assess(data, mime)
    ex = extract_document(slot, data, mime) if q.ok else None
    ex_d = ex.model_dump() if ex is not None else {}
    checks = validators.doc_checks(slot, ex_d, q)
    return ex_d, checks, q


def evaluate(app: KycApplication) -> tuple[list[CheckResult], Decision]:
    d = get_data()
    per_doc = [c for slot in app.docs for c in app.doc_checks.get(slot, [])]
    failed = {slot for slot, cs in app.doc_checks.items() if any(c.status == "FAIL" for c in cs)}
    cross = validators.cross_checks(app.path, app.docs, failed, app.declared_gstin, app.declared_udyam, d.gstin, d.udyam)
    checks = per_doc + cross
    return checks, decide(checks)
