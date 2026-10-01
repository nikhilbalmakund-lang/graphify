"""Claude provider (Anthropic Messages API, official `anthropic` SDK).

* Structured output via `output_config.format` (JSON schema); the result is
  re-validated with Pydantic and against the input data afterwards.
* Opus/Sonnet 5.x run with adaptive thinking (the default) and an explicit
  effort level; temperature is not sent to those models.
* Server-side refusal fallbacks (`fallbacks="default"`) are enabled for the
  models that support them; disable with CLAUDE_REFUSAL_FALLBACK=false.
* Stop reasons are checked before content is read (refusal / max_tokens).
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import anthropic
from pydantic import BaseModel

from ai.orchestration.router import ModelRouter
from ai.prompts.registry import PromptTemplate
from ai.providers.base import (
    AIProvider,
    AIProviderError,
    AIStatus,
    ImageInput,
    ProviderHealthInfo,
    ToolExecutor,
    ToolSpec,
    ToolTrace,
)
from ai.schemas.outputs import strict_json_schema

FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1")
EFFORT_MODELS = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
)
NO_SAMPLING_MODELS = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
)


class ClaudeProvider(AIProvider):
    name = "claude"
    label = "Claude (Anthropic)"

    def __init__(
        self,
        router: ModelRouter,
        api_key: str | None,
        timeout: float = 180.0,
        refusal_fallback: bool = True,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        super().__init__(router)
        self._key = api_key or ""
        self.refusal_fallback = refusal_fallback
        self._client = client
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._key) or self._client is not None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._key, timeout=self._timeout, max_retries=2)
        return self._client

    def settings_for(self, prompt: PromptTemplate) -> dict[str, Any]:
        model = self.router.model_for(self.name, prompt.tier)
        out: dict[str, Any] = {"max_tokens": prompt.max_tokens}
        if model.startswith(EFFORT_MODELS) and prompt.claude_effort:
            out["effort"] = prompt.claude_effort
        if not model.startswith(NO_SAMPLING_MODELS):
            out["temperature"] = prompt.temperature
        if self.refusal_fallback and model.startswith(FALLBACK_MODELS):
            out["fallbacks"] = "default"
        return out

    async def validate(self) -> ProviderHealthInfo:
        models = self.router.table().get(self.name, {})
        if not self.configured:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.NOT_CONFIGURED,
                detail="ANTHROPIC_API_KEY not set",
                models=models,
            )
        started = time.perf_counter()
        try:
            for model in sorted(set(models.values())):
                await self.client.models.retrieve(model)
        except anthropic.AuthenticationError:
            return ProviderHealthInfo(
                provider=self.name, status=AIStatus.ERROR, detail="Invalid Anthropic API key", models=models
            )
        except anthropic.PermissionDeniedError:
            return ProviderHealthInfo(
                provider=self.name, status=AIStatus.ERROR, detail="API key lacks permission", models=models
            )
        except anthropic.NotFoundError:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.ERROR,
                detail="A configured Claude model was not found; check CLAUDE_MODEL_* settings",
                models=models,
            )
        except anthropic.APIConnectionError:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.ERROR,
                detail="Cannot reach the Anthropic API",
                models=models,
            )
        except anthropic.APIStatusError as exc:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.ERROR,
                detail=f"Anthropic API error {exc.status_code}",
                models=models,
            )
        return ProviderHealthInfo(
            provider=self.name,
            status=AIStatus.CONNECTED,
            detail="Credentials and models verified",
            models=models,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    def _request(self, prompt: PromptTemplate, model: str, schema: type[BaseModel]) -> dict[str, Any]:
        settings = self.settings_for(prompt)
        output_config: dict[str, Any] = {
            "format": {"type": "json_schema", "schema": strict_json_schema(schema)}
        }
        if "effort" in settings:
            output_config["effort"] = settings["effort"]
        req: dict[str, Any] = {
            "model": model,
            "max_tokens": prompt.max_tokens,
            "system": prompt.system,
            "output_config": output_config,
        }
        if "temperature" in settings:
            req["temperature"] = settings["temperature"]
        return req

    async def _create(self, req: dict[str, Any]) -> Any:
        try:
            if self.refusal_fallback and req["model"].startswith(FALLBACK_MODELS):
                return await self.client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **req
                )
            return await self.client.messages.create(**req)
        except anthropic.AuthenticationError as exc:
            raise AIProviderError("AI_PROVIDER_UNAVAILABLE", "Invalid Anthropic API key", self.name) from exc
        except anthropic.RateLimitError as exc:
            raise AIProviderError(
                "AI_RATE_LIMITED", "Anthropic rate limit reached; retry later", self.name
            ) from exc
        except anthropic.BadRequestError as exc:
            raise AIProviderError(
                "AI_BAD_REQUEST", f"Anthropic rejected the request: {exc.message}", self.name
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE", f"Anthropic API error {exc.status_code}", self.name
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE", "Cannot reach the Anthropic API", self.name
            ) from exc

    def _check_stop(self, resp: Any) -> None:
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise AIProviderError(
                "AI_REFUSAL", f"Claude declined the request (category: {category})", self.name
            )
        if resp.stop_reason == "max_tokens":
            raise AIProviderError("AI_INVALID_OUTPUT", "Claude output was truncated (max_tokens)", self.name)

    @staticmethod
    def _text(resp: Any) -> str:
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    async def _generate(
        self,
        prompt: PromptTemplate,
        model: str,
        user_text: str,
        schema: type[BaseModel],
        images: list[ImageInput] | None,
    ) -> tuple[str, int | None, int | None, str]:
        content: list[dict[str, Any]] = []
        for img in images or []:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.mime_type,
                        "data": base64.standard_b64encode(img.data).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": f"{prompt.instructions}\n\n{user_text}"})
        req = self._request(prompt, model, schema)
        req["messages"] = [{"role": "user", "content": content}]
        resp = await self._create(req)
        self._check_stop(resp)
        return self._text(resp), resp.usage.input_tokens, resp.usage.output_tokens, resp.model

    async def _tool_loop(
        self,
        prompt: PromptTemplate,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        final_schema: type[BaseModel],
        max_turns: int,
    ) -> tuple[str, list[ToolTrace], int | None, int | None, str]:
        req = self._request(prompt, model, final_schema)
        req["system"] = f"{prompt.system}\n\n{prompt.instructions}"
        req["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
        ]
        convo = list(messages)
        trace: list[ToolTrace] = []
        tin = tout = 0
        served = model
        for _ in range(max_turns):
            resp = await self._create({**req, "messages": convo})
            tin += resp.usage.input_tokens or 0
            tout += resp.usage.output_tokens or 0
            served = resp.model
            if resp.stop_reason == "refusal":
                self._check_stop(resp)
            if resp.stop_reason in ("tool_use", "pause_turn"):
                convo.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason == "pause_turn":
                    continue
                calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
                results = await asyncio.gather(
                    *(self._run_tool(executor, c.name, dict(c.input or {}), trace) for c in calls)
                )
                convo.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": c.id,
                                "content": json.dumps(r[0], default=str),
                                "is_error": not r[1],
                            }
                            for c, r in zip(calls, results, strict=True)
                        ],
                    }
                )
                continue
            self._check_stop(resp)
            return self._text(resp), trace, tin, tout, served
        raise AIProviderError("AI_TOOL_LOOP_LIMIT", f"Tool loop exceeded {max_turns} turns", self.name)

    @staticmethod
    async def _run_tool(
        executor: ToolExecutor, name: str, args: dict[str, Any], trace: list[ToolTrace]
    ) -> tuple[dict[str, Any], bool]:
        started = time.perf_counter()
        try:
            out = await executor(name, args)
            ok = "error" not in out
        except Exception as exc:  # tool failures are reported to the model, never raised to the user
            out, ok = {"error": f"{type(exc).__name__}: tool failed"}, False
        trace.append(
            ToolTrace(
                name=name,
                arguments=args,
                ok=ok,
                summary=str(out.get("summary", "")) if isinstance(out, dict) else "",
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        )
        return out, ok
