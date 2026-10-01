"""Server configuration from environment variables.

Secrets live only in the server environment (`.env`, or the git-ignored
`.secrets.env` written by the Settings page). They are never sent to the
browser; the API reports only whether each key is configured.
Every value is optional so the application always starts in DEMO MODE.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "data"
# Both files can be relocated (Docker volume, isolated test runs) without code changes.
ENV_FILE = Path(os.environ.get("NEXUS_ENV_FILE") or PROJECT_ROOT / ".env")
SECRETS_FILE = Path(os.environ.get("NEXUS_SECRETS_FILE") or PROJECT_ROOT / ".secrets.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), str(SECRETS_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "NEXUS Trading Intelligence"
    app_short_name: str = "NEXUS"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # NoDecode: accept "a,b" as well as a JSON list (see _split).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = ""
    redis_url: str = ""

    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    claude_model_fast: str = "claude-haiku-4-5"
    claude_model_strong: str = "claude-opus-5-5"
    gemini_model_fast: str = "gemini-3.8-flash"
    gemini_model_strong: str = "gemini-3.1-pro-preview"
    claude_refusal_fallback: bool = True

    market_data_provider: str = "demo"
    market_data_api_key: SecretStr | None = None
    market_data_symbol_map: str = ""
    market_data_ttl_multiplier: float = 1.0
    news_provider: str = "demo"
    news_api_key: SecretStr | None = None
    economic_calendar_provider: str = "demo"
    economic_calendar_api_key: SecretStr | None = None

    broker: str = "paper"
    broker_api_key: SecretStr | None = None
    broker_api_secret: SecretStr | None = None
    live_trading_enabled: bool = False

    default_market: str = "XAUUSD"
    default_timeframe: str = "15m"
    risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    paper_starting_balance: float = 100_000.0

    rate_limit_ai_per_minute: int = 20
    rate_limit_backtest_per_minute: int = 10
    rate_limit_market_per_minute: int = 600
    rate_limit_default_per_minute: int = 300

    data_retention_days: int | None = None
    background_tasks: bool = True
    build_memory_on_startup: bool = True
    signal_scan_interval_seconds: int = 60
    quote_broadcast_interval_seconds: float = 2.0
    max_upload_mb: int = 8

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                return json.loads(s)
            return [x.strip() for x in s.split(",") if x.strip()]
        return v

    @field_validator("data_retention_days", mode="before")
    @classmethod
    def _empty_none(cls, v: object) -> object:
        return None if v in ("", None) else v

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("sqlite:///") and "+aiosqlite" not in url:
                url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{DATA_DIR / 'nexus.db'}"

    @property
    def sync_database_url(self) -> str:
        return self.resolved_database_url.replace("+aiosqlite", "").replace("+asyncpg", "")

    def secret(self, name: str) -> str | None:
        val = getattr(self, name, None)
        if isinstance(val, SecretStr):
            raw = val.get_secret_value().strip()
            return raw or None
        return None

    def symbol_overrides(self) -> dict[str, dict[str, str]]:
        if not self.market_data_symbol_map.strip():
            return {}
        try:
            data = json.loads(self.market_data_symbol_map)
        except ValueError:
            return {}
        return {self.market_data_provider: {str(k).upper(): str(v) for k, v in data.items()}}


@lru_cache
def get_settings() -> Settings:
    return Settings()
