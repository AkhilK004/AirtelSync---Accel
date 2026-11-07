from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.engine.pricing import EngineError


class ApiError(Exception):
    """Error format (PLAN 6.4): {"error": {"code", "message_key", "params"}}."""

    def __init__(self, status: int, code: str, message_key: str, params: dict | None = None, text: str = ""):
        self.status, self.code, self.message_key, self.params, self.text = status, code, message_key, params or {}, text


def _body(code, key, params, text):
    return {"error": {"code": code, "message_key": key, "params": params, "message": text}}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse(_body(e.code, e.message_key, e.params, e.text), status_code=e.status)

    @app.exception_handler(EngineError)
    async def _eng(_: Request, e: EngineError):
        return JSONResponse(_body(e.code, e.message_key, e.params, e.text), status_code=e.status)
