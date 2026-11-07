from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.advisor import service
from app.advisor.models import AdvisorReply, AdvisorSession
from app.analytics.events import log_event
from app.config import ASSISTED_CALLBACK_HOURS, MAX_MESSAGES_PER_SESSION
from app.errors import ApiError
from app.leads.service import create_lead

router = APIRouter(prefix="/advisor", tags=["advisor"])


class StartBody(BaseModel):
    language: str | None = None
    channel: str | None = None
    partner_code: str | None = Field(None, max_length=40)


class MessageBody(BaseModel):
    text: str = Field(..., max_length=500)


class HandoffBody(BaseModel):
    phone: str | None = Field(None, max_length=20)
    preferred_time: str | None = Field(None, max_length=40)


def _get(sid: str) -> AdvisorSession:
    s = service.load_session(sid)
    if not s:
        raise ApiError(404, "SESSION_NOT_FOUND", "advisor.session_not_found")
    return s


@router.post("/sessions", response_model=AdvisorReply)
def start(body: StartBody | None = None):
    b = body or StartBody()
    return service.start_session(b.language, b.channel, b.partner_code)


@router.post("/sessions/{sid}/messages", response_model=AdvisorReply)
def message(sid: str, body: MessageBody):
    s = _get(sid)
    if s.messages >= MAX_MESSAGES_PER_SESSION:  # simple per-session rate limit
        raise ApiError(429, "RATE_LIMITED", "advisor.rate_limited")
    return service.handle_message(s, body.text)


@router.get("/sessions/{sid}")
def state(sid: str):
    s = _get(sid)
    return {"session_id": s.id, "language": s.language, "slots": s.slots, "quote_id": s.quote_id, "recommended": s.recommended,
            "questions_asked": s.questions_asked, "lead_id": s.lead_id, "assumptions": list(s.assumptions)}


@router.post("/sessions/{sid}/handoff")
def handoff(sid: str, body: HandoffBody):
    s = _get(sid)
    lead_id = create_lead(s, "requested_human", None, stage="quote" if s.recommended else "advisor", phone=body.phone, preferred_time=body.preferred_time)
    s.lead_id = lead_id
    service.save_session(s)
    log_event("handoff_requested", s.id, {"reason": "form"})
    return {"lead_id": lead_id, "callback_hours": ASSISTED_CALLBACK_HOURS}
