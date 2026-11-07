from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.analytics.events import log_event
from app.orders import service

router = APIRouter(prefix="/orders", tags=["orders"])
LANG = Query("en", pattern="^(en|hi|mr)$")


class Access(BaseModel):
    phone_last4: str = Field(..., pattern=r"^\d{4}$")


class RescheduleBody(Access):
    slot_date: date
    slot_window: str


@router.get("/{order_id}")
def get_order(order_id: str, phone_last4: str | None = None, lang: str = LANG, track: bool = False):
    """Tracker view. Lightweight access check: the last 4 digits of the phone used at checkout.
    `track=true` marks a real tracker page-load (not a poll) for the 'status checks per order' funnel metric."""
    o = service.load(order_id)
    service.check_access(o, phone_last4)
    if track:
        log_event("tracker_viewed", order_id, {})
    return service.view(o, lang)


@router.post("/{order_id}/reschedule")
def reschedule(order_id: str, body: RescheduleBody, lang: str = LANG):
    o = service.load(order_id)
    service.check_access(o, body.phone_last4)
    return service.view(service.reschedule(o, body.slot_date, body.slot_window), lang)


@router.post("/{order_id}/callback")
def callback(order_id: str, body: Access):
    o = service.load(order_id)
    service.check_access(o, body.phone_last4)
    return service.request_callback(o)
