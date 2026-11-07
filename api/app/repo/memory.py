from __future__ import annotations

import copy
from collections import defaultdict


class MemoryRepo:
    def __init__(self) -> None:
        self._c: dict[str, dict[str, dict]] = defaultdict(dict)

    def put(self, collection: str, doc_id: str, doc: dict) -> None:
        self._c[collection][doc_id] = copy.deepcopy(doc)

    def get(self, collection: str, doc_id: str) -> dict | None:
        d = self._c[collection].get(doc_id)
        return copy.deepcopy(d) if d is not None else None

    def list(self, collection: str) -> list[dict]:
        return [copy.deepcopy(d) for d in self._c[collection].values()]

    def append(self, collection: str, doc_id: str, doc: dict) -> None:
        if doc_id in self._c[collection]:
            raise ValueError(f"{collection}/{doc_id} already exists (append-only)")
        self._c[collection][doc_id] = copy.deepcopy(doc)

    def clear(self) -> None:
        self._c.clear()
