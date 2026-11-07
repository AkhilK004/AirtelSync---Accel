from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.pricing import build_quote, make_quote, toggled_quote
from app.errors import ApiError
from app.models.engine import Profile, Quote, QuoteState, ToggleResult
from app.repo import get_repo

router = APIRouter(prefix="/quotes", tags=["quotes"])


class ToggleBody(BaseModel):
    sku: str
    on: bool


def _load(quote_id: str) -> QuoteState:
    d = get_repo().get("quotes", quote_id)
    if not d:
        raise ApiError(404, "QUOTE_NOT_FOUND", "quote.not_found")
    return QuoteState.model_validate(d)


@router.post("", response_model=Quote)
def create_quote(profile: Profile):
    state, quote = make_quote(profile)
    get_repo().put("quotes", state.id, state.model_dump(mode="json"))
    return quote


@router.get("/{quote_id}", response_model=Quote)
def get_quote(quote_id: str):
    return build_quote(_load(quote_id))


@router.post("/{quote_id}/toggle", response_model=ToggleResult)
def toggle_addon(quote_id: str, body: ToggleBody):
    state, result = toggled_quote(_load(quote_id), body.sku, body.on)
    get_repo().put("quotes", state.id, state.model_dump(mode="json"))
    return result
