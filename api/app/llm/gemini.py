"""Gemini via google-genai (Vertex AI in asia-south1, or AI Studio key as fallback). Not exercised offline."""
from __future__ import annotations

import json

from pydantic import BaseModel

from app.config import settings
from app.llm.base import ImagePart

TIMEOUT_MS = 15_000


class GeminiClient:
    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        self._types = types
        if settings.GOOGLE_API_KEY and not settings.GCP_PROJECT:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        else:
            self.client = genai.Client(vertexai=True, project=settings.GCP_PROJECT, location=settings.GCP_LOCATION,
                                       http_options=types.HttpOptions(timeout=TIMEOUT_MS))

    def _call(self, contents, config):
        last = None
        for _ in range(2):  # one retry
            try:
                return self.client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
            except Exception as e:  # noqa: BLE001
                last = e
        raise last

    def extract(self, system: str, user_parts: list, schema: type[BaseModel]) -> BaseModel:
        t = self._types
        cfg = t.GenerateContentConfig(system_instruction=system, temperature=0, response_mime_type="application/json", response_schema=schema)
        parts = [t.Part.from_bytes(data=p.data, mime_type=p.mime) if isinstance(p, ImagePart) else p for p in user_parts]
        resp = self._call(parts, cfg)
        if resp.parsed is not None:
            return resp.parsed
        return schema.model_validate_json(resp.text)

    def generate(self, system: str, facts: dict, language: str) -> str:
        t = self._types
        cfg = t.GenerateContentConfig(system_instruction=system, temperature=0.2)
        payload = {k: v for k, v in facts.items() if k != "template_text"}
        resp = self._call([f"FACTS:\n{json.dumps(payload, ensure_ascii=False)}"], cfg)
        return (resp.text or "").strip()
