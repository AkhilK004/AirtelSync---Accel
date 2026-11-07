"""Offline LLM stand-in: rule-based NLU, template NLG, and fixture-based document extraction.

Document extraction returns a human transcription of the 47 specimen images (data/derived/kyc_fixture.json, keyed by file sha256).
An image that is not in the fixture is "unreadable" (confidence 0). This proves the KYC validators, not live OCR accuracy.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from pydantic import BaseModel

from app.advisor.slots import DERIVED, SlotUpdate
from app.llm.base import ImagePart
from app.llm.rules_nlu import parse


@lru_cache(maxsize=1)
def _fixture() -> dict:
    p = DERIVED / "kyc_fixture.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


class FakeLLM:
    def extract(self, system: str, user_parts: list, schema: type[BaseModel]) -> BaseModel:
        img = next((p for p in user_parts if isinstance(p, ImagePart)), None)
        if img is not None:
            hit = _fixture().get(hashlib.sha256(img.data).hexdigest())
            return schema.model_validate(hit["extract"]) if hit else schema.model_validate({"confidence": 0.0})
        if schema is not SlotUpdate:
            raise NotImplementedError(schema)
        payload = json.loads(user_parts[0]) if isinstance(user_parts[0], str) else user_parts[0]
        return parse(payload["message"], payload.get("pending_slot"))

    def generate(self, system: str, facts: dict, language: str) -> str:
        return facts["template_text"]
