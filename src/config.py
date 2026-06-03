"""
Configuration centralisée.

Charge depuis .env via pydantic-settings (typage strict + validation).
Importable partout : `from src.config import settings`.
"""
from functools import lru_cache
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "sport_data"
    postgres_user: str = "etl_writer"
    postgres_password: SecretStr = SecretStr("change-me")

    # Google Maps
    google_maps_api_key: SecretStr = SecretStr("")
    company_address: str = "1362 Avenue des Platanes, 34970 Lattes, France"

    # Slack
    slack_webhook_url: SecretStr = SecretStr("")
    slack_channel: str = "#sport-data"

    # Métier — paramètres modifiables sans redéploiement.
    prime_rate_default: float = Field(0.05, ge=0.0, le=1.0)
    wellbeing_activity_threshold: int = Field(15, ge=1)
    walking_max_km: float = Field(15.0, gt=0)
    cycling_max_km: float = Field(25.0, gt=0)

    # Générateur
    activities_seed: int = 42
    activities_total: int = Field(4000, ge=500, le=20000)

    # PII
    pii_hash_salt: SecretStr = SecretStr("dev-salt-change-in-prod")

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
