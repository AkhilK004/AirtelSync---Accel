"""Gemini via google-genai (Vertex AI in asia-south1, or AI Studio key as fallback). Not exercised offline."""
from __future__ import annotations

import json
import time

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
        """Up to 3 attempts. Transient errors (429 rate limit, 5xx) wait 1 s then 3 s; anything else fails fast."""
        last = None
        for attempt in range(3):
            try:
                return self.client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
            except Exception as e:  # noqa: BLE001
                last = e
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                if attempt == 2 or (code is not None and code not in (408, 429, 500, 502, 503, 504)):
                    break
                time.sleep(1 if attempt == 0 else 3)
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
