import os

from fastapi import APIRouter

from app.data.loaders import get_data

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "build": os.getenv("BUILD_SHA", "dev"), "counts": get_data().counts()}
