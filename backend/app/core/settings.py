from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "IoT Device Management Server"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://iotadmin:secretpassword@db:5432/iot_dms"

    # CORS: comma-separated list of allowed frontend origins.
    # e.g. CORS_ORIGINS="https://app.example.com,https://admin.example.com"
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Telemetry Alerting Thresholds
    ALERT_LOW_BATTERY_PCT: float = 20.0
    ALERT_HIGH_TEMP_C: float = 65.0
    ALERT_LOW_VOLTAGE_V: float = 11.5

    # Offline watchdog: a device is marked OFFLINE after missing
    # DEVICE_OFFLINE_GRACE_MULTIPLIER consecutive expected uploads
    # (threshold = device.upload_interval_seconds * multiplier).
    DEVICE_OFFLINE_GRACE_MULTIPLIER: float = 3.0
    OFFLINE_WATCHDOG_INTERVAL_SECONDS: int = 60

    # Telemetry retention: raw telemetry rows older than this are pruned by the
    # retention worker. Set high enough to cover your longest analytics window.
    # Set to 0 to disable pruning entirely.
    TELEMETRY_RETENTION_DAYS: int = 90
    # Resolved alerts older than this are pruned (unresolved alerts are kept).
    ALERT_RETENTION_DAYS: int = 180
    # How often the retention worker sweeps.
    RETENTION_SWEEP_INTERVAL_SECONDS: int = 86400  # once per day
    # Delete in batches so a large sweep never holds a huge transaction.
    RETENTION_BATCH_SIZE: int = 10000

    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # Optional admin bootstrap credentials (used by scripts/create_admin.py).
    ADMIN_EMAIL: str = "admin@pcb.local"
    ADMIN_PASSWORD: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: Union[str, List[str]]) -> List[str]:
        # Allow a plain comma-separated string in the env var.
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
