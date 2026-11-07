"""Checks -> decision (PLAN 5e). Deterministic; the LLM never decides."""
from __future__ import annotations

from app.models.kyc import CheckResult, Decision

KYC_REVIEW_HOURS = 24


def decide(checks: list[CheckResult]) -> Decision:
    fails = [c for c in checks if c.status == "FAIL"]
    warns = [c for c in checks if c.status == "WARN"]
    if any(c.code == "GSTIN_STATUS" for c in fails):
        return Decision(status="REJECTED", reason_codes=["GSTIN_STATUS"])
    fixable = [c for c in fails if c.fix_key]
    if fixable:
        return Decision(status="ACTION_REQUIRED", reason_codes=sorted({c.code for c in fixable}))
    if fails or len(warns) >= 2:
        return Decision(status="MANUAL_REVIEW", reason_codes=sorted({c.code for c in fails + warns}), review_hours=KYC_REVIEW_HOURS)
    return Decision(status="APPROVED", reason_codes=[])
