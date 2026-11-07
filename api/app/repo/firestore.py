"""Firestore (Native mode, asia-south1) implementation of the Repo protocol. One Firestore collection per logical collection,
document id = our ULID-like id. Documents are plain JSON-able dicts (the services already store model_dump(mode="json"))."""
from __future__ import annotations

from typing import Any

from app.config import settings


class FirestoreRepo:
    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            from google.cloud import firestore  # type: ignore

            client = firestore.Client(project=settings.GCP_PROJECT or None)
        self.db = client

    def put(self, collection: str, doc_id: str, doc: dict) -> None:
        self.db.collection(collection).document(doc_id).set(doc)

    def get(self, collection: str, doc_id: str) -> dict | None:
        snap = self.db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def list(self, collection: str) -> list[dict]:
        return [s.to_dict() for s in self.db.collection(collection).stream()]

    def append(self, collection: str, doc_id: str, doc: dict) -> None:
        """Append-only: Firestore `create` fails with AlreadyExists if the id is taken."""
        try:
            self.db.collection(collection).document(doc_id).create(doc)
        except Exception as e:  # google.api_core.exceptions.AlreadyExists
            if type(e).__name__ == "AlreadyExists":
                raise ValueError(f"{collection}/{doc_id} already exists (append-only)") from e
            raise

    def clear(self) -> None:
        """Demo reset: delete every document in the app's collections. Never called outside /admin/reset."""
        for name in ("sessions", "quotes", "orders", "consents", "kyc_applications", "leads", "events", "audit_log", "meta"):
            for snap in self.db.collection(name).stream():
                snap.reference.delete()
