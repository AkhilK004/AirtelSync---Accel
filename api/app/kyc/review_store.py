"""Manual-review images only. Everything else is processed in memory and never persisted (PLAN 3, 5c).

Local/dev: files under api/.review_store with an expiry sidecar. Prod: GCS bucket in asia-south1 with a 1-day lifecycle rule
(the bucket rule is the real enforcement; purge_expired() is the local equivalent).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.config import API_ROOT, settings

TTL_SECONDS = 24 * 3600
_DIR = API_ROOT / ".review_store"


def put(order_id: str, slot: str, data: bytes, mime: str) -> str:
    key = f"{order_id}/{slot}"
    if settings.APP_ENV == "prod" and settings.GCS_REVIEW_BUCKET:
        from google.cloud import storage  # type: ignore

        storage.Client(project=settings.GCP_PROJECT or None).bucket(settings.GCS_REVIEW_BUCKET).blob(key).upload_from_string(data, content_type=mime)
        return f"gcs://{settings.GCS_REVIEW_BUCKET}/{key}"
    path = _DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    (path.parent / f"{slot}.meta.json").write_text(json.dumps({"mime": mime, "expires_at": time.time() + TTL_SECONDS}))
    return f"local://{key}"


def purge_expired(now: float | None = None) -> int:
    now = now or time.time()
    n = 0
    if not _DIR.exists():
        return 0
    for meta in _DIR.glob("*/*.meta.json"):
        if json.loads(meta.read_text()).get("expires_at", 0) <= now:
            (meta.parent / meta.name.replace(".meta.json", "")).unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
            n += 1
    return n
