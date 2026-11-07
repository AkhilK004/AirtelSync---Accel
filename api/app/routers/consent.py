from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.analytics.events import log_event
from app.consent import service

router = APIRouter(prefix="/consents", tags=["consent"])


class GrantBody(BaseModel):
    order_id: str
    purposes: list[str]
    language: str = "en"
    channel: str = "web"


class WithdrawBody(BaseModel):
    purposes: list[str]


@router.get("/notice")
def notice(lang: str = Query("en", pattern="^(en|hi|mr)$"), partner: bool = False):
    return service.notice(lang, partner)


@router.post("")
def grant(body: GrantBody):
    rec = service.grant(body.order_id, body.purposes, body.language, body.channel)
    log_event("consent_given", body.order_id, {"purposes": rec["purposes"], "notice_version": rec["notice_version"]})
    return rec


@router.get("/{order_id}")
def get(order_id: str):
    return {"order_id": order_id, "ledger": service.ledger(order_id), "effective": sorted(service.effective(order_id))}


@router.post("/{consent_id}/withdraw")
def withdraw(consent_id: str, body: WithdrawBody):
    return service.withdraw(consent_id, body.purposes)
