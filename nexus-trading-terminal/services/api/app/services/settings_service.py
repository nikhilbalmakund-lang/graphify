"""Runtime settings (database) and server-side secrets (git-ignored .secrets.env)."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import SECRETS_FILE, Settings
from app.core.database import Database, utcnow
from app.models import AppSetting
from app.schemas.settings import CATEGORIES, PROVIDER_KEYS, SECRET_KEYS, SecretStatus


class SettingsService:
    def __init__(self, db: Database, env: Settings):
        self.db = db
        self.env = env
        self._cache: dict[str, BaseModel] = {}

    def _defaults(self, category: str) -> BaseModel:
        model = CATEGORIES[category]
        if category == "risk":
            return model(max_risk_per_trade=self.env.risk_per_trade, max_daily_loss=self.env.max_daily_loss)  # type: ignore[call-arg]
        if category == "markets":
            return model(default_timeframe=self.env.default_timeframe)  # type: ignore[call-arg]
        if category == "paper":
            return model(starting_balance=self.env.paper_starting_balance)  # type: ignore[call-arg]
        return model()

    async def load(self) -> None:
        async with self.db.session() as s:
            rows = {r.key: r.value for r in (await s.execute(select(AppSetting))).scalars()}
        for cat, model in CATEGORIES.items():
            base = self._defaults(cat).model_dump()
            stored = rows.get(cat) or {}
            try:
                self._cache[cat] = model.model_validate({**base, **stored})
            except ValueError:
                self._cache[cat] = self._defaults(cat)
        # The live-trading UI switch always starts OFF after a restart.
        self._cache["live_trading"] = CATEGORIES["live_trading"]()

    def get(self, category: str) -> Any:
        if category not in self._cache:
            self._cache[category] = self._defaults(category)
        return self._cache[category]

    def all(self) -> dict[str, dict[str, Any]]:
        return {cat: self.get(cat).model_dump(mode="json") for cat in CATEGORIES}

    async def update(self, category: str, values: dict[str, Any]) -> tuple[BaseModel, dict[str, Any]]:
        if category not in CATEGORIES:
            raise KeyError(category)
        current = self.get(category).model_dump()
        merged = {**current, **values}
        new = CATEGORIES[category].model_validate(merged)
        diff = {
            k: {"from": current.get(k), "to": v} for k, v in new.model_dump().items() if current.get(k) != v
        }
        if category != "live_trading":
            async with self.db.session() as s:
                row = await s.get(AppSetting, category)
                if row is None:
                    s.add(AppSetting(key=category, value=new.model_dump(mode="json"), updated_at=utcnow()))
                else:
                    row.value = new.model_dump(mode="json")
                    row.updated_at = utcnow()
        self._cache[category] = new
        return new, diff

    async def import_all(self, data: dict[str, dict[str, Any]]) -> list[str]:
        changed = []
        for cat, values in data.items():
            if cat in CATEGORIES and cat != "live_trading" and isinstance(values, dict):
                await self.update(cat, values)
                changed.append(cat)
        return changed


class SecretsService:
    """Writes provider keys to a git-ignored env file with owner-only permissions.

    Keys are applied to the running process environment so providers can be
    re-validated without code changes. Full keys are never returned.
    """

    def __init__(self, path: Path = SECRETS_FILE):
        self.path = path

    def _read(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
        return out

    def write(self, values: dict[str, str | None]) -> list[str]:
        data = self._read()
        changed = []
        for k, v in values.items():
            if v is None or v.strip() == "":
                if k in data:
                    data.pop(k)
                    changed.append(k)
                os.environ.pop(k, None)
            else:
                data[k] = v.strip()
                os.environ[k] = v.strip()
                changed.append(k)
        body = "# NEXUS server-side secrets (written by the Settings page). Never commit this file.\n"
        body += "".join(f"{k}={v}\n" for k, v in sorted(data.items()))
        self.path.write_text(body, encoding="utf-8")
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        return changed

    @staticmethod
    def status(env: Settings) -> list[SecretStatus]:
        out = []
        for key in SECRET_KEYS:
            val = env.secret(key.lower())
            out.append(
                SecretStatus(
                    key=key, configured=bool(val), hint=f"****{val[-4:]}" if val and len(val) >= 8 else None
                )
            )
        return out

    @staticmethod
    def providers(env: Settings) -> dict[str, str]:
        return {k: str(getattr(env, k.lower(), "")) for k in PROVIDER_KEYS}
