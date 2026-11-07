from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.advisor.slots import Slots
from app.models.engine import Note


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdvisorSession(BaseModel):
    id: str
    language: str = "en"
    language_locked: bool = False
    channel: str | None = None
    partner_code: str | None = None
    slots: Slots = Field(default_factory=Slots)
    assumptions: dict[str, Note] = {}   # slot -> note
    questions_asked: int = 0
    pending_slot: str | None = None
    tools_done: bool = False
    confusion: int = 0
    messages: int = 0
    recommended: bool = False
    quote_id: str | None = None
    profile_sig: str | None = None
    lead_id: str | None = None
    history: list[dict] = []            # [{role, text}] (capped)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class QuickReply(BaseModel):
    label: str
    value: str


class Progress(BaseModel):
    asked: int
    total: int


class RecLine(BaseModel):
    sku: str
    name: str
    qty: int
    reason: str
    line_monthly_display: str


class RecSummary(BaseModel):
    bundle_name: str
    segment: str
    lines: list[RecLine]
    addon_names: list[str]
    monthly_total_display: str
    monthly_total_paise: int
    one_time_total_display: str
    contract_months: int
    assisted: bool
    skipped: list[str]


class BudgetInfo(BaseModel):
    budget_display: str
    cheapest_display: str
    gap_display: str | None
    over_budget_by_extras: bool


class AdvisorReply(BaseModel):
    session_id: str
    message: str
    quick_replies: list[QuickReply]
    progress: Progress
    action: str
    language: str
    recommendation: RecSummary | None = None
    quote_id: str | None = None
    handoff: bool = False
    lead_id: str | None = None
    assumptions: list[str] = []          # assumption keys, for the UI chips / tests
    assumption_texts: list[str] = []
    budget: BudgetInfo | None = None
    fallback_used: bool = False          # True when the LLM reply failed the post-check
