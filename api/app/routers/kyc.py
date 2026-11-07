from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel, Field

from app.kyc import quality, service

router = APIRouter(prefix="/kyc", tags=["kyc"])
LANG = Query("en", pattern="^(en|hi|mr)$")


class GstinBody(BaseModel):
    gstin: str = Field(..., max_length=40)


class UdyamBody(BaseModel):
    udyam_number: str = Field(..., max_length=40)


class PathBody(BaseModel):
    path: str = Field(..., pattern="^(gstin|udyam|pan)$")


@router.get("/{order_id}")
def get_state(order_id: str, lang: str = LANG):
    return service.view(order_id, lang)


@router.put("/{order_id}/path")
def set_path(order_id: str, body: PathBody, lang: str = LANG):
    return service.set_path(order_id, body.path, lang)


@router.post("/{order_id}/lookup/gstin")
def lookup_gstin(order_id: str, body: GstinBody, lang: str = LANG):
    return service.lookup_gstin(order_id, body.gstin, lang)


@router.post("/{order_id}/lookup/udyam")
def lookup_udyam(order_id: str, body: UdyamBody, lang: str = LANG):
    return service.lookup_udyam(order_id, body.udyam_number, lang)


@router.post("/{order_id}/documents")
async def upload(order_id: str, slot: str = Form(...), file: UploadFile = File(...), lang: str = LANG):
    data = await file.read(quality.MAX_BYTES + 1)  # bounded read; content type is sniffed, not trusted
    return service.upload(order_id, slot, data, lang)


@router.post("/{order_id}/evaluate")
def evaluate(order_id: str, lang: str = LANG):
    return service.evaluate(order_id, lang)
