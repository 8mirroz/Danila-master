import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

class Settings:
    @property
    def ENVIRONMENT(self) -> str:
        return os.environ.get("PARTSOPS_ENV", os.environ.get("ENV", "")).lower()

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT in ("prod", "production")

    @property
    def AUTH_MODE(self) -> str:
        configured = os.environ.get("PARTSOPS_AUTH_MODE", "").strip().lower()
        if configured:
            return configured
        return "oidc" if self.IS_PRODUCTION else "legacy"

    @property
    def OIDC_ISSUER(self) -> str:
        return os.environ.get("PARTSOPS_OIDC_ISSUER", "").rstrip("/")

    @property
    def OIDC_AUDIENCE(self) -> str:
        return os.environ.get("PARTSOPS_OIDC_AUDIENCE", "").strip()

    @property
    def OIDC_TENANT_CLAIM(self) -> str:
        return os.environ.get("PARTSOPS_OIDC_TENANT_CLAIM", "organization_id").strip()

    @property
    def OIDC_ROLE_CLAIM(self) -> str:
        return os.environ.get("PARTSOPS_OIDC_ROLE_CLAIM", "realm_access.roles").strip()

    @property
    def OIDC_JWKS_URL(self) -> str:
        configured = os.environ.get("PARTSOPS_OIDC_JWKS_URL", "").strip()
        if configured:
            return configured
        return f"{self.OIDC_ISSUER}/protocol/openid-connect/certs" if self.OIDC_ISSUER else ""

    @property
    def ALLOW_MASTER_TOKEN_PLATFORM_ADMIN(self) -> bool:
        return os.environ.get("PARTSOPS_ALLOW_MASTER_TOKEN_PLATFORM_ADMIN", "false").lower() in ("true", "1", "yes")

    def validate_auth_configuration(self) -> None:
        if self.AUTH_MODE not in {"legacy", "oidc"}:
            raise RuntimeError("PARTSOPS_AUTH_MODE must be either legacy or oidc")
        if self.IS_PRODUCTION and self.AUTH_MODE != "oidc":
            raise RuntimeError("PARTSOPS_AUTH_MODE=oidc is required when PARTSOPS_ENV=production")
        if self.AUTH_MODE == "oidc" and (not self.OIDC_ISSUER or not self.OIDC_AUDIENCE):
            raise RuntimeError(
                "PARTSOPS_OIDC_ISSUER and PARTSOPS_OIDC_AUDIENCE are required when PARTSOPS_AUTH_MODE=oidc"
            )
        if self.STORAGE_BACKEND not in {"local", "s3"}:
            raise RuntimeError("PARTSOPS_STORAGE_BACKEND must be either local or s3")
        if self.IS_PRODUCTION and self.STORAGE_BACKEND != "s3":
            raise RuntimeError("PARTSOPS_STORAGE_BACKEND=s3 is required when PARTSOPS_ENV=production")
        if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET:
            raise RuntimeError("PARTSOPS_S3_BUCKET is required when PARTSOPS_STORAGE_BACKEND=s3")

    @property
    def TESTING(self) -> bool:
        return os.environ.get("TESTING") == "1"

    @property
    def DATABASE_URL(self) -> str:
        env_url = os.environ.get("DATABASE_URL")
        if self.IS_PRODUCTION and not (env_url and env_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))):
            raise RuntimeError("PostgreSQL DATABASE_URL is required when PARTSOPS_ENV=production")
        if env_url and env_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
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
    def STORAGE_BACKEND(self) -> str:
        return os.environ.get("PARTSOPS_STORAGE_BACKEND", "local").strip().lower()

    @property
    def S3_BUCKET(self) -> str:
        return os.environ.get("PARTSOPS_S3_BUCKET", "").strip()

    @property
    def S3_ENDPOINT_URL(self) -> str:
        return os.environ.get("PARTSOPS_S3_ENDPOINT_URL", "").strip()

    @property
    def S3_REGION(self) -> str:
        return os.environ.get("PARTSOPS_S3_REGION", "ru-central1").strip()

    @property
    def S3_PREFIX(self) -> str:
        return os.environ.get("PARTSOPS_S3_PREFIX", "partsops").strip("/")

    @property
    def ENABLE_STRICT_UPLOAD_VALIDATION(self) -> bool:
        return os.environ.get("ENABLE_STRICT_UPLOAD_VALIDATION", "true").lower() in ("true", "1", "yes")

    @property
    def ENABLE_STRICT_TENANT_ENFORCEMENT(self) -> bool:
        return os.environ.get("ENABLE_STRICT_TENANT_ENFORCEMENT", "true").lower() in ("true", "1", "yes")

    @property
    def CORS_ALLOW_ORIGINS(self) -> str:
        return os.environ.get("CORS_ALLOW_ORIGINS") or os.environ.get("PARTSOPS_CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000,http://127.0.0.1:3000"

    @property
    def MAX_PARSE_ROWS(self) -> int:
        try:
            return int(os.environ.get("MAX_PARSE_ROWS", "50000"))
        except ValueError:
            return 50000

    @property
    def PHASE_LABEL(self) -> str:
        # Reflect current product stage (override via PARTSOPS_PHASE_LABEL)
        return os.environ.get("PARTSOPS_PHASE_LABEL") or "Phase 2 — QuoteOps Beta Hardening"

    @property
    def HERMES_API_URL(self) -> str:
        return os.environ.get("HERMES_API_URL") or "http://127.0.0.1:8642"

    @property
    def HERMES_API_KEY(self) -> str:
        return os.environ.get("HERMES_API_KEY") or ""

    @property
    def COPILOT_TIMEOUT_SECONDS(self) -> int:
        try:
            return int(os.environ.get("COPILOT_TIMEOUT_SECONDS", "45"))
        except ValueError:
            return 45

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

    @property
    def OUTBOUND_WEBHOOK_SECRET(self) -> str:
        return os.environ.get("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", "")

    @property
    def OUTBOUND_WEBHOOK_TIMEOUT_SECONDS(self) -> float:
        try:
            return max(1.0, float(os.environ.get("PARTSOPS_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS", "10")))
        except ValueError:
            return 10.0

    @property
    def OUTBOUND_WEBHOOK_ALLOWED_HOSTS(self) -> set[str]:
        return {value.strip().lower() for value in os.environ.get("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "").split(",") if value.strip()}

# Global singleton
settings = Settings()
