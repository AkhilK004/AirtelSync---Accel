from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMClient(Protocol):
    def extract(self, system: str, user_parts: list, schema: type[BaseModel]) -> BaseModel: ...

    def generate(self, system: str, facts: dict, language: str) -> str: ...
