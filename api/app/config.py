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
    RATE_LIMIT_ENABLED: bool = True
    SEED_ON_START: bool = False  # demo: seed back-office leads + 3 live orders at startup

    # Tunable business constants (see docs/assumptions.md)
    TODAY: str = "2026-07-15"  # dataset README: "today" for date checks
    BILL_MAX_AGE_DAYS: int = 90
    NAME_MATCH_PASS: int = 90
    NAME_MATCH_WARN: int = 75
    MAX_QUESTIONS: int = 6
    ABANDON_MINUTES: int = 10
    MOCK_LATENCY_MS_MIN: int = 300
    MOCK_LATENCY_MS_MAX: int = 600

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR)
        return p if p.is_absolute() else (API_ROOT / p).resolve()


settings = Settings()

# --- Phase 2 engine constants (documented in docs/assumptions.md) ---
MULTI_SITE_MIN_LOCATIONS = 3   # data: all multi-site leads have 3-12 sites; others have 1-2
MULTI_SITE_MAX_LOCATIONS = 10  # above this -> assisted (field force); plan default
PRICE_POINT_RULE = "midpoint"  # unit price = midpoint of [min,max] rounded half-up to whole rupee
ASSISTED_CALLBACK_HOURS = 4

# generic business-type keywords used only when the type is not in the leads data (docs/assumptions.md A20)
MANUFACTURING_KEYWORDS = ("manufactur", "factory", "workshop", "plant", "unit")
PROFESSIONAL_KEYWORDS = ("clinic", "doctor", "lab", "office", "firm", "studio", "agency", "centre", "center", "consult", "academy")
MAX_MESSAGES_PER_SESSION = 80

# --- checkout (mock) ---
MOCK_OTP = "123456"
SLOT_WINDOWS = ("morning", "evening")
MAX_SLOT_DAYS_AHEAD = 30
PAYMENT_MODES = ("pay_on_activation", "upi_mock")
