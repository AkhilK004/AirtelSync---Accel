"""Ops / demo endpoints, protected by X-Admin-Token."""
from datetime import date

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.audit import audit
from app.config import settings
from app.errors import ApiError
from app.orders import service

router = APIRouter(prefix="/admin", tags=["admin"])
LANG = Query("en", pattern="^(en|hi|mr)$")


def _auth(token: str | None) -> None:
    if not token or token != settings.ADMIN_TOKEN:
        raise ApiError(401, "ADMIN_AUTH", "admin.unauthorized")


class SlotBody(BaseModel):
    slot_date: date
    slot_window: str


@router.post("/orders/{order_id}/advance")
def advance(order_id: str, x_admin_token: str | None = Header(None), lang: str = LANG):
    _auth(x_admin_token)
    o = service.advance(order_id)
    audit("admin", "order_advance", order_id, {"state": o["state"]})
    return service.view(o, lang)


@router.post("/orders/{order_id}/reschedule")
def reschedule(order_id: str, body: SlotBody, x_admin_token: str | None = Header(None), lang: str = LANG):
    _auth(x_admin_token)
    o = service.reschedule(service.load(order_id), body.slot_date, body.slot_window)
    audit("admin", "order_reschedule", order_id, {"slot": o["slot"]})
    return service.view(o, lang)


@router.post("/orders/{order_id}/hold")
def hold(order_id: str, x_admin_token: str | None = Header(None), lang: str = LANG):
    _auth(x_admin_token)
    o = service.hold(order_id)
    audit("admin", "order_hold", order_id, {})
    return service.view(o, lang)


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: str, x_admin_token: str | None = Header(None), lang: str = LANG):
    _auth(x_admin_token)
    o = service.cancel(order_id, "cancelled_by_ops")
    audit("admin", "order_cancel", order_id, {})
    return service.view(o, lang)


@router.post("/reset")
def reset(x_admin_token: str | None = Header(None)):
    """Demo: wipe the in-memory store and re-seed back-office leads and the 3 demo orders."""
    _auth(x_admin_token)
    from app.seed import seed_demo
    return seed_demo(reset=True)
