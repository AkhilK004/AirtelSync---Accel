import asyncio
import random
import re

from fastapi import APIRouter

from app.config import settings
from app.data.loaders import get_data
from app.errors import ApiError
from app.models.domain import GstinRecord, UdyamRecord

router = APIRouter(prefix="/mock", tags=["mock-registries"])


def normalise_gstin(raw: str) -> str:
    return re.sub(r"[\s\-]", "", raw).upper()


def normalise_udyam(raw: str) -> str:
    """Accepts 'udyam-kl-00-3078801', 'UDYAM KL 00 3078801', 'UDYAMKL003078801'."""
    s = re.sub(r"[\s\-_]", "", raw).upper()
    m = re.fullmatch(r"UDYAM([A-Z]{2})(\d{2})(\d{7})", s)
    return f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else s


async def _latency() -> None:
    if settings.MOCK_LATENCY_MS_MAX > 0:
        await asyncio.sleep(random.randint(settings.MOCK_LATENCY_MS_MIN, settings.MOCK_LATENCY_MS_MAX) / 1000)


@router.get("/gstin/{gstin}", response_model=GstinRecord)
async def lookup_gstin(gstin: str):
    await _latency()
    rec = get_data().gstin.get(normalise_gstin(gstin))
    if not rec:
        raise ApiError(404, "GSTIN_NOT_FOUND", "mock.gstin_not_found")
    return rec


@router.get("/udyam/{udyam_no}", response_model=UdyamRecord)
async def lookup_udyam(udyam_no: str):
    await _latency()
    rec = get_data().udyam.get(normalise_udyam(udyam_no))
    if not rec:
        raise ApiError(404, "UDYAM_NOT_FOUND", "mock.udyam_not_found")
    return rec
