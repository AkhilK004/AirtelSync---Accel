"""Deterministic dialogue manager. The LLM never picks the next step."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.advisor.models import AdvisorSession
from app.advisor.slots import REQUIRED_ORDER, SlotUpdate, Slots
from app.config import settings

MAX_CONFUSION = 3


@dataclass(frozen=True)
class Action:
    kind: Literal["ASK", "RECOMMEND", "EXPLAIN", "HANDOFF", "CLARIFY"]
    slot: str | None = None


def missing_slots(s: Slots) -> list[str]:
    return [k for k in REQUIRED_ORDER if getattr(s, k) is None]


def next_action(sess: AdvisorSession, update: SlotUpdate, progressed: bool) -> Action:
    if update.intent == "request_human":
        return Action("HANDOFF")
    if sess.recommended:
        return Action("EXPLAIN") if update.intent == "ask_why" else Action("RECOMMEND")
    missing = missing_slots(sess.slots)
    if not missing:
        return Action("RECOMMEND")
    if not progressed:
        if sess.confusion >= MAX_CONFUSION:
            return Action("HANDOFF")
        return Action("CLARIFY", sess.pending_slot or missing[0])
    if sess.questions_asked >= settings.MAX_QUESTIONS:
        return Action("RECOMMEND")  # service applies defaults + assumptions for what is still missing
    return Action("ASK", missing[0])
