from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import Container
from app.main import create_app
from app.services.settings_service import SecretsService

FIXED_NOW = datetime(2026, 10, 1, 14, 30, 27, tzinfo=UTC)  # Thursday, markets open


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("nexus")
    env = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp / 'test.db'}",
        background_tasks=False,
        log_json=False,
        build_memory_on_startup=False,
        rate_limit_ai_per_minute=1000,
        rate_limit_backtest_per_minute=1000,
        anthropic_api_key=None,
        gemini_api_key=None,
    )
    container = Container(env, clock=lambda: FIXED_NOW)
    container.secrets = SecretsService(tmp / ".secrets.env")
    app = create_app(env, container=container, run_background=False)
    with TestClient(app) as c:
        c.container = container  # type: ignore[attr-defined]
        yield c
