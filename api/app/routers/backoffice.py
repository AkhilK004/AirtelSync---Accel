"""Back-office API (English-only UI). HTTP Basic auth; every state change is audit-logged."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from app.analytics.funnel import compute
from app.config import settings
from app.errors import ApiError
from app.leads import service

security = HTTPBasic(auto_error=False)


def auth(creds: Annotated[HTTPBasicCredentials | None, Depends(security)]) -> str:
    ok = creds is not None and secrets.compare_digest(creds.username.encode(), settings.BACKOFFICE_USER.encode()) \
        and secrets.compare_digest(creds.password.encode(), settings.BACKOFFICE_PASSWORD.encode())
    if not ok:
        raise ApiError(401, "BACKOFFICE_AUTH", "backoffice.unauthorized")
    return creds.username  # type: ignore[union-attr]


router = APIRouter(prefix="/backoffice", tags=["backoffice"], dependencies=[Depends(auth)])


class StatusBody(BaseModel):
    status: str = Field(..., pattern="^(new|contacted|won|lost)$")


@router.get("/me")
def me(user: Annotated[str, Depends(auth)]):
    return {"user": user}


@router.get("/leads")
def leads(route: str | None = None, segment: str | None = None, stage: str | None = None, status: str | None = None):
    return {"leads": service.list_leads(route, segment, stage, status)}


@router.get("/leads/{lead_id}")
def lead(lead_id: str):
    return service.detail(lead_id)


@router.post("/leads/{lead_id}/status")
def set_status(lead_id: str, body: StatusBody, user: Annotated[str, Depends(auth)]):
    return service.set_status(lead_id, body.status, user)


@router.get("/funnel")
def funnel():
    return compute()
