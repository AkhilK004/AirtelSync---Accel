from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "local"
    STORAGE: str = "memory"
    LLM_PROVIDER: str = "gemini"
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GCP_PROJECT: str = ""
    GCP_LOCATION: str = "asia-south1"
    GOOGLE_API_KEY: str = ""
    GCS_REVIEW_BUCKET: str = ""
    BACKOFFICE_USER: str = "admin"
    BACKOFFICE_PASSWORD: str = "change-me"
    ADMIN_TOKEN: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3000"
    GST_RATE: float = 0.18
    DATA_DIR: str = "../data/raw"

    # Tunable business constants (see docs/assumptions.md)
    TODAY: str = "2026-07-15"  # dataset README: "today" for date checks
    BILL_MAX_AGE_DAYS: int = 90
    NAME_MATCH_PASS: int = 90
    NAME_MATCH_WARN: int = 75
    MAX_QUESTIONS: int = 6
    ABANDON_MINUTES: int = 10

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR)
        return p if p.is_absolute() else (API_ROOT / p).resolve()


settings = Settings()
