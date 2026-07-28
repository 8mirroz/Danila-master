import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

class Settings:
    @property
    def TESTING(self) -> bool:
        return os.environ.get("TESTING") == "1"

    @property
    def DATABASE_URL(self) -> str:
        env_url = os.environ.get("DATABASE_URL")
        if env_url and env_url.startswith(("postgresql://", "postgres://")):
            return env_url
        if self.TESTING:
            return "sqlite:///test_database.db"
        return env_url or "sqlite:///database.db"

    @property
    def DB_POOL_SIZE(self) -> int:
        try:
            return int(os.environ.get("DB_POOL_SIZE", "10"))
        except ValueError:
            return 10

    @property
    def DB_MAX_OVERFLOW(self) -> int:
        try:
            return int(os.environ.get("DB_MAX_OVERFLOW", "20"))
        except ValueError:
            return 20

    @property
    def DB_POOL_RECYCLE_SECONDS(self) -> int:
        try:
            return int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800"))
        except ValueError:
            return 1800

    @property
    def MAX_UPLOAD_SIZE_MB(self) -> int:
        try:
            return int(os.environ.get("MAX_UPLOAD_SIZE_MB", "15"))
        except ValueError:
            return 15

    @property
    def UPLOAD_ALLOWED_EXTENSIONS(self) -> list[str]:
        raw = os.environ.get("UPLOAD_ALLOWED_EXTENSIONS") or "pdf,xlsx,csv,jpg,jpeg,png"
        return [ext.strip().lower().lstrip('.') for ext in raw.split(",") if ext.strip()]

    @property
    def UPLOAD_DIR(self) -> str:
        return os.environ.get("UPLOAD_DIR") or "08_DATA/uploads"

    @property
    def ENABLE_STRICT_UPLOAD_VALIDATION(self) -> bool:
        return os.environ.get("ENABLE_STRICT_UPLOAD_VALIDATION", "true").lower() in ("true", "1", "yes")

    @property
    def ENABLE_STRICT_TENANT_ENFORCEMENT(self) -> bool:
        return os.environ.get("ENABLE_STRICT_TENANT_ENFORCEMENT", "true").lower() in ("true", "1", "yes")

    @property
    def CORS_ALLOW_ORIGINS(self) -> str:
        return os.environ.get("CORS_ALLOW_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000,http://127.0.0.1:3000"

    @property
    def MAX_PARSE_ROWS(self) -> int:
        try:
            return int(os.environ.get("MAX_PARSE_ROWS", "50000"))
        except ValueError:
            return 50000

    @property
    def PHASE_LABEL(self) -> str:
        return os.environ.get("PARTSOPS_PHASE_LABEL") or "Phase 0 — Stabilization"

    @property
    def HERMES_API_URL(self) -> str:
        return os.environ.get("HERMES_API_URL") or "http://127.0.0.1:8642"

    @property
    def HERMES_API_KEY(self) -> str:
        return os.environ.get("HERMES_API_KEY") or "partsops-hermes-secret-key"

    @property
    def COPILOT_DAILY_BUDGET_USD(self) -> float:
        try:
            return float(os.environ.get("COPILOT_DAILY_BUDGET_USD", "10.0"))
        except ValueError:
            return 10.0

    @property
    def COPILOT_RPM_LIMIT(self) -> int:
        try:
            return int(os.environ.get("COPILOT_RPM_LIMIT", "10"))
        except ValueError:
            return 10

    @property
    def COPILOT_MAX_CONCURRENT_RUNS(self) -> int:
        try:
            return int(os.environ.get("COPILOT_MAX_CONCURRENT_RUNS", "2"))
        except ValueError:
            return 2

# Global singleton
settings = Settings()