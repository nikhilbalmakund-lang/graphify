"""Model routing: simple tasks -> fast/cheaper model, complex analysis -> strong model.

Models are configuration, not code. Defaults can be overridden with
CLAUDE_MODEL_FAST / CLAUDE_MODEL_STRONG / GEMINI_MODEL_FAST / GEMINI_MODEL_STRONG.
"""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "claude": {"fast": "claude-haiku-4-5", "strong": "claude-opus-5-5"},
    "gemini": {"fast": "gemini-3.8-flash", "strong": "gemini-3.1-pro-preview"},
}

TASK_TIERS: dict[str, str] = {
    "signal_analysis": "strong",
    "critic": "strong",
    "chart_analysis": "strong",
    "research": "strong",
    "chat": "strong",
    "briefing": "fast",
    "news_sentiment": "fast",
    "explain": "fast",
}


class ModelRouter(BaseModel):
    models: dict[str, dict[str, str]] = DEFAULT_MODELS

    def model_for(self, provider: str, tier: str) -> str:
        table = self.models.get(provider) or DEFAULT_MODELS.get(provider)
        if not table:
            raise KeyError(f"No models configured for provider '{provider}'")
        return table.get(tier) or table["strong"]

    def table(self) -> dict[str, dict[str, str]]:
        return {p: dict(v) for p, v in self.models.items()}
