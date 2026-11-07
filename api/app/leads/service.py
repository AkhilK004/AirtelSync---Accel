"""Lead creation (scoring and the back-office list arrive in Phase 7)."""
from __future__ import annotations

from app.advisor.models import AdvisorSession, now_iso
from app.engine.pricing import new_id
from app.repo import get_repo


def route_for(segment: str | None, partner_code: str | None) -> str:
    if segment in ("multi_site", "manufacturer"):
        return "field_sales"
    return "partner" if partner_code else "telesales"


def create_lead(sess: AdvisorSession, reason: str, segment: str | None, stage: str = "advisor",
                phone: str | None = None, preferred_time: str | None = None) -> str:
    repo = get_repo()
    existing = repo.get("leads", sess.lead_id) if sess.lead_id else None
    if existing:  # one lead per session; enrich it
        existing.update({k: v for k, v in (("phone", phone), ("preferred_time", preferred_time)) if v})
        if reason == "requested_human":
            existing["reason"] = reason
        repo.put("leads", existing["id"], existing)
        return existing["id"]
    lid = new_id()
    repo.put("leads", lid, {
        "id": lid, "created_at": now_iso(), "session_id": sess.id, "profile": sess.slots.model_dump(), "segment": segment,
        "stage_reached": stage, "reason": reason, "quote_id": sess.quote_id, "order_id": None, "score": None, "score_reasons": [],
        "route_to": route_for(segment, sess.partner_code), "partner_code": sess.partner_code, "status": "new",
        "phone": phone, "preferred_time": preferred_time,
    })
    return lid
