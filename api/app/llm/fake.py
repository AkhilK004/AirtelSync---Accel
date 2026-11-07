"""Offline LLM stand-in: rule-based NLU + template NLG. Keeps pytest and scenarios runnable with no credentials."""
from __future__ import annotations

import json

from pydantic import BaseModel

from app.advisor.slots import SlotUpdate
from app.llm.rules_nlu import parse


class FakeLLM:
    def extract(self, system: str, user_parts: list, schema: type[BaseModel]) -> BaseModel:
        if schema is not SlotUpdate:
            raise NotImplementedError(schema)
        payload = json.loads(user_parts[0]) if isinstance(user_parts[0], str) else user_parts[0]
        return parse(payload["message"], payload.get("pending_slot"))

    def generate(self, system: str, facts: dict, language: str) -> str:
        return facts["template_text"]
