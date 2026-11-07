from __future__ import annotations

from typing import Protocol


class Repo(Protocol):
    """Document store. Collections: sessions, quotes, orders, consents, kyc_applications, leads, events, audit_log."""

    def put(self, collection: str, doc_id: str, doc: dict) -> None: ...
    def get(self, collection: str, doc_id: str) -> dict | None: ...
    def list(self, collection: str) -> list[dict]: ...
    def append(self, collection: str, doc_id: str, doc: dict) -> None:
        """Append-only write (consents, audit log): fails if the id already exists."""
        ...
