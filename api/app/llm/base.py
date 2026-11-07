from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class ImagePart:
    """Provider-neutral image input for extraction."""
    data: bytes
    mime: str


class LLMClient(Protocol):
    def extract(self, system: str, user_parts: list, schema: type[BaseModel]) -> BaseModel: ...

    def generate(self, system: str, facts: dict, language: str) -> str: ...
