"""Append-only audit log for back-office / ops actions and KYC decisions (PLAN 6.8). No PII in details."""
from __future__ import annotations

from app import clock
from app.engine.pricing import new_id
from app.repo import get_repo


def audit(actor: str, action: str, ref_id: str, details: dict | None = None) -> None:
    get_repo().append("audit_log", new_id(), {"ts": clock.now_iso(), "actor": actor, "action": action, "order_id": ref_id, "details": details or {}})
