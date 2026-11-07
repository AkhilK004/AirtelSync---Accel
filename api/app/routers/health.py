import os

from fastapi import APIRouter

from app.config import MAX_SLOT_DAYS_AHEAD, settings
from app.data.loaders import get_data

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "build": os.getenv("BUILD_SHA", "dev"), "counts": get_data().counts()}


@router.get("/meta")
def meta():
    """App-wide constants the UI needs. `today` is the dataset date (2026-07-15), not the wall clock."""
    return {"today": settings.TODAY, "max_slot_days": MAX_SLOT_DAYS_AHEAD}
