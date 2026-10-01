"""Gemini provider (official `google-genai` SDK).

* Structured output via response_mime_type=application/json plus a JSON schema.
* Tool use: function declarations with automatic function calling disabled -
  the application executes only its own read-only tools. Because JSON-schema
  output and function calling are not always combinable, the tool loop ends
  with one formatting call (no tools) that returns the schema-shaped answer.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
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

MAX_OUTPUT_TOKENS = 16_000


class GeminiProvider(AIProvider):
    name = "gemini"
    label = "Gemini (Google)"

    def __init__(self, router: ModelRouter, api_key: str | None, client: Any | None = None):
        super().__init__(router)
        self._key = api_key or ""
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self._key) or self._client is not None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = genai.Client(api_key=self._key)
        return self._client

    def settings_for(self, prompt: PromptTemplate) -> dict[str, Any]:
        return {
            "max_output_tokens": min(prompt.max_tokens, MAX_OUTPUT_TOKENS),
            "temperature": prompt.temperature,
        }

    async def validate(self) -> ProviderHealthInfo:
        models = self.router.table().get(self.name, {})
        if not self.configured:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.NOT_CONFIGURED,
                detail="GEMINI_API_KEY not set",
                models=models,
            )
        started = time.perf_counter()
        try:
            for model in sorted(set(models.values())):
                await self.client.aio.models.get(model=model)
        except genai_errors.ClientError as exc:
            code = getattr(exc, "code", None)
            detail = "Invalid Gemini API key" if code in (400, 401, 403) else f"Gemini API error {code}"
            if code == 404:
                detail = "A configured Gemini model was not found; check GEMINI_MODEL_* settings"
            return ProviderHealthInfo(provider=self.name, status=AIStatus.ERROR, detail=detail, models=models)
        except genai_errors.APIError as exc:
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.ERROR,
                detail=f"Gemini API error {getattr(exc, 'code', '')}",
                models=models,
            )
        except Exception as exc:  # network failures surface as generic exceptions in the SDK
            return ProviderHealthInfo(
                provider=self.name,
                status=AIStatus.ERROR,
                detail=f"Cannot reach the Gemini API ({type(exc).__name__})",
                models=models,
            )
        return ProviderHealthInfo(
            provider=self.name,
            status=AIStatus.CONNECTED,
            detail="Credentials and models verified",
            models=models,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    def _config(
        self,
        prompt: PromptTemplate,
        schema: type[BaseModel] | None,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
    ) -> types.GenerateContentConfig:
        kwargs: dict[str, Any] = {
            "system_instruction": system or prompt.system,
            "temperature": prompt.temperature,
            "max_output_tokens": min(prompt.max_tokens, MAX_OUTPUT_TOKENS),
        }
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_json_schema"] = strict_json_schema(schema)
        if tools:
            kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name, description=t.description, parameters_json_schema=t.parameters
                        )
                        for t in tools
                    ]
                )
            ]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        return types.GenerateContentConfig(**kwargs)

    async def _call(self, model: str, contents: Any, config: types.GenerateContentConfig) -> Any:
        try:
            return await self.client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except genai_errors.ClientError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                raise AIProviderError(
                    "AI_RATE_LIMITED", "Gemini rate limit reached; retry later", self.name
                ) from exc
            raise AIProviderError(
                "AI_BAD_REQUEST" if code == 400 else "AI_PROVIDER_UNAVAILABLE",
                f"Gemini API error {code}",
                self.name,
            ) from exc
        except genai_errors.APIError as exc:
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE", f"Gemini API error {getattr(exc, 'code', '')}", self.name
            ) from exc

    def _final_text(self, resp: Any) -> str:
        try:
            text = resp.text
        except (ValueError, AttributeError):
            text = None
        if not text:
            reason = None
            if getattr(resp, "candidates", None):
                reason = getattr(resp.candidates[0], "finish_reason", None)
            raise AIProviderError(
                "AI_REFUSAL", f"Gemini returned no text (finish reason: {reason})", self.name
            )
        return text

    @staticmethod
    def _usage(resp: Any) -> tuple[int | None, int | None]:
        meta = getattr(resp, "usage_metadata", None)
        if meta is None:
            return None, None
        return meta.prompt_token_count, (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)

    async def _generate(
        self,
        prompt: PromptTemplate,
        model: str,
        user_text: str,
        schema: type[BaseModel],
        images: list[ImageInput] | None,
    ) -> tuple[str, int | None, int | None, str]:
        parts: list[Any] = [types.Part.from_bytes(data=i.data, mime_type=i.mime_type) for i in images or []]
        parts.append(f"{prompt.instructions}\n\n{user_text}")
        resp = await self._call(model, parts, self._config(prompt, schema))
        tin, tout = self._usage(resp)
        return self._final_text(resp), tin, tout, getattr(resp, "model_version", None) or model

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
        system = f"{prompt.system}\n\n{prompt.instructions}"
        contents: list[types.Content] = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=str(m["content"]))],
            )
            for m in messages
        ]
        trace: list[ToolTrace] = []
        tin = tout = 0
        for _ in range(max_turns):
            resp = await self._call(model, contents, self._config(prompt, None, system, tools))
            a, b = self._usage(resp)
            tin += a or 0
            tout += b or 0
            calls = list(resp.function_calls or [])
            if not calls:
                break
            contents.append(resp.candidates[0].content)
            results = await asyncio.gather(
                *(self._run_tool(executor, c.name, dict(c.args or {}), trace) for c in calls)
            )
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(name=c.name, response={"result": r})
                        for c, r in zip(calls, results, strict=True)
                    ],
                )
            )
        else:
            raise AIProviderError("AI_TOOL_LOOP_LIMIT", f"Tool loop exceeded {max_turns} turns", self.name)
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text="Now give your final answer strictly as JSON matching the response schema, using only the tool results above."
                    )
                ],
            )
        )
        final = await self._call(model, contents, self._config(prompt, final_schema, system))
        a, b = self._usage(final)
        return (
            self._final_text(final),
            trace,
            tin + (a or 0),
            tout + (b or 0),
            getattr(final, "model_version", None) or model,
        )

    @staticmethod
    async def _run_tool(
        executor: ToolExecutor, name: str, args: dict[str, Any], trace: list[ToolTrace]
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            out = await executor(name, args)
            ok = "error" not in out
        except Exception as exc:
            out, ok = {"error": f"{type(exc).__name__}: tool failed"}, False
        trace.append(
            ToolTrace(
                name=name,
                arguments=args,
                ok=ok,
                summary=str(out.get("summary", "")),
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        )
        return json.loads(json.dumps(out, default=str))
