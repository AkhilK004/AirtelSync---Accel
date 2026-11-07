"""Funnel events. No PII in props (PLAN 6.3)."""
from __future__ import annotations

from app.advisor.models import now_iso
from app.engine.pricing import new_id
from app.repo import get_repo

EVENT_NAMES = {"advisor_started", "slot_filled", "recommendation_shown", "quote_viewed", "addon_toggled", "quote_accepted",
               "checkout_completed", "consent_given", "kyc_doc_uploaded", "kyc_decided", "order_state_changed",
               "tracker_viewed", "handoff_requested", "quote_shared"}


_SEEDING = False  # set by app/seed.py so demo events are flagged (props.seed) and the funnel panel can say so


def set_seeding(on: bool) -> None:
    global _SEEDING
    _SEEDING = on


def log_event(name: str, ref_id: str, props: dict | None = None) -> None:
    assert name in EVENT_NAMES, name
    p = dict(props or {})
    if _SEEDING:
        p["seed"] = True
    get_repo().put("events", new_id(), {"ts": now_iso(), "name": name, "ref_id": ref_id, "props": p})
