"""AI cost estimation.

Claude prices are Anthropic first-party list prices (USD per million tokens)
as published at the time of writing. Gemini prices are intentionally not
hard-coded: set AI_PRICING_JSON (e.g. {"gemini-3.8-flash": [0.3, 2.5]}) to
enable estimates. Unknown models report cost as None ("not available")
rather than a guessed number.
"""

from __future__ import annotations

import json
import os

PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def _overrides() -> dict[str, tuple[float, float]]:
    raw = os.environ.get("AI_PRICING_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k): (float(v[0]), float(v[1])) for k, v in data.items()}
    except (ValueError, TypeError, IndexError, KeyError):
        return {}


def estimate_cost(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    table = {**PRICING_PER_MTOK, **_overrides()}
    price = table.get(model)
    if price is None:
        # Served model names may carry suffixes; match on prefix.
        price = next((v for k, v in table.items() if model.startswith(k)), None)
    if price is None:
        return None
    return round(input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1], 6)
