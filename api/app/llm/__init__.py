from functools import lru_cache

from app.config import settings
from app.llm.base import LLMClient


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    if settings.LLM_PROVIDER == "fake":
        from app.llm.fake import FakeLLM
        return FakeLLM()
    from app.llm.gemini import GeminiClient
    return GeminiClient()
