import json
from types import SimpleNamespace

import pytest

from ai.critic.validation import validate_signal_analysis
from ai.orchestration.analysts import AIReviewOrchestrator
from ai.orchestration.chat import AIChatAgent
from ai.orchestration.consensus import Agreement, AIConsensusEngine
from ai.orchestration.router import ModelRouter
from ai.orchestration.services import AIChartAnalyzer, AIExplainer, BriefingWriter
from ai.orchestration.tools import FORBIDDEN_TOOLS, TOOLS
from ai.orchestration.usage import estimate_cost
from ai.prompts.registry import GROUNDING_RULES, PROMPTS
from ai.providers.base import AIProviderError, ImageInput, ToolSpec
from ai.providers.claude.provider import ClaudeProvider
from ai.providers.demo import DemoRuleBasedProvider
from ai.providers.gemini.provider import GeminiProvider
from ai.schemas.outputs import CriticVerdict, SignalAnalysis, strict_json_schema

PAYLOAD = {
    "symbol": "XAUUSD",
    "timeframe": "15m",
    "price": 2350.0,
    "is_demo": True,
    "features": {"atr14": 4.0, "ema20": 2348.0, "vwap": 2346.5},
    "structure": {"supports": [{"price": 2340.0}], "resistances": [{"price": 2362.0}]},
    "quant": {
        "direction": "LONG",
        "levels": {
            "entry_price": 2350.2,
            "stop": 2338.9,
            "effective_rr": 2.1,
            "targets": [{"price": 2362.0}, {"price": 2371.0}],
        },
    },
    "events": {"next_high_impact_minutes": None},
    "data_quality": {"usable": True, "quality_score": 1.0},
    "historical_evidence": {"sample_size": 40, "sample_label": "MODERATE"},
}


def analysis(direction="LONG", **kw):
    base = dict(
        direction=direction,
        reasoning=["1H trend bullish; price above VWAP 2346.5"],
        supporting_factors=["Support at 2340.0 held"],
        opposing_factors=["Resistance 2362.0 overhead"],
        key_risks=["DEMO data only"],
        invalidation="15m close below 2340.0",
        analysis_quality="MEDIUM",
        disagreements=[],
        referenced_prices=[2340.0, 2362.0],
    )
    base.update(kw)
    return base


# ------------------------------------------------------------------ fakes
class FakeAnthropic:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        outer = self

        class _Msgs:
            async def create(self, **kw):
                outer.calls.append(("messages", kw))
                return outer.responses.pop(0)

        class _BetaMsgs:
            async def create(self, **kw):
                outer.calls.append(("beta", kw))
                return outer.responses.pop(0)

        class _Models:
            async def retrieve(self, model):
                return SimpleNamespace(id=model)

        self.messages = _Msgs()
        self.beta = SimpleNamespace(messages=_BetaMsgs())
        self.models = _Models()


def claude_text(data, stop="end_turn", model="claude-opus-5-5"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(data))],
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        model=model,
        stop_details=None,
    )


class FakeGemini:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        outer = self

        class _Models:
            async def generate_content(self, model, contents, config):
                outer.calls.append((model, contents, config))
                return outer.responses.pop(0)

            async def get(self, model):
                return SimpleNamespace(name=model)

        self.aio = SimpleNamespace(models=_Models())


def gemini_text(data):
    return SimpleNamespace(
        text=json.dumps(data),
        function_calls=None,
        candidates=[],
        usage_metadata=SimpleNamespace(
            prompt_token_count=500, candidates_token_count=100, thoughts_token_count=20
        ),
        model_version="gemini-3.1-pro-preview",
    )


ROUTER = ModelRouter()


# ------------------------------------------------------------------ tests
def test_strict_schema_is_self_contained():
    def walk(node):
        if isinstance(node, dict):
            assert "$ref" not in node and "title" not in node
            if node.get("type") == "object" and "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for model in (SignalAnalysis, CriticVerdict):
        walk(strict_json_schema(model))


def test_prompts_are_versioned_and_grounded():
    for p in PROMPTS.values():
        assert p.name and p.version and p.date and p.tier in ("fast", "strong")
        assert GROUNDING_RULES in p.system


def test_no_execution_tools_exposed():
    assert all(t.read_only for t in TOOLS)
    assert not ({t.name for t in TOOLS} & FORBIDDEN_TOOLS)


def test_cost_estimation():
    assert estimate_cost("claude", "claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(24.0)
    assert estimate_cost("gemini", "gemini-unknown", 100, 100) is None
    assert estimate_cost("claude", "claude-opus-5-5", None, 5) is None


async def test_claude_structured_analysis_with_fallback_beta():
    fake = FakeAnthropic([claude_text(analysis())])
    p = ClaudeProvider(ROUTER, None, client=fake)
    res = await p.analyze_signal(PAYLOAD)
    kind, kw = fake.calls[0]
    assert kind == "beta" and kw["fallbacks"] == "default" and kw["model"] == "claude-opus-5-5"
    assert (
        kw["output_config"]["format"]["type"] == "json_schema" and kw["output_config"]["effort"] == "medium"
    )
    assert "temperature" not in kw
    assert res.data["direction"] == "LONG" and res.usage.cost_usd == pytest.approx(
        1000 / 1e6 * 4 + 200 / 1e6 * 20
    )
    assert res.prompt["prompt_name"] == "signal_analysis" and res.prompt["prompt_version"] == "1.0.0"


async def test_claude_fast_tier_uses_standard_endpoint():
    brief = {
        "theme": "t",
        "strongest_trends": [],
        "volatility": "v",
        "major_risks": [],
        "upcoming_events": [],
        "assets_to_monitor": [],
        "facts": [],
        "interpretation": [],
        "uncertainty": [],
    }
    fake = FakeAnthropic([claude_text(brief, model="claude-haiku-4-5")])
    res = await ClaudeProvider(ROUTER, None, client=fake).summarize_market({"assets": []})
    kind, kw = fake.calls[0]
    assert kind == "messages" and kw["model"] == "claude-haiku-4-5" and "temperature" in kw
    assert "effort" not in kw["output_config"]
    assert res.model == "claude-haiku-4-5"


async def test_claude_refusal_and_invalid_output_are_errors():
    refusal = claude_text({}, stop="refusal")
    with pytest.raises(AIProviderError) as e1:
        await ClaudeProvider(ROUTER, None, client=FakeAnthropic([refusal])).analyze_signal(PAYLOAD)
    assert e1.value.code == "AI_REFUSAL"
    bad = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="not json")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        model="claude-opus-5-5",
    )
    with pytest.raises(AIProviderError) as e2:
        await ClaudeProvider(ROUTER, None, client=FakeAnthropic([bad])).analyze_signal(PAYLOAD)
    assert e2.value.code == "AI_INVALID_OUTPUT"
    wrong = claude_text({"direction": "MAYBE"})
    with pytest.raises(AIProviderError) as e3:
        await ClaudeProvider(ROUTER, None, client=FakeAnthropic([wrong])).analyze_signal(PAYLOAD)
    assert e3.value.code == "AI_INVALID_OUTPUT"


async def test_claude_tool_loop_executes_read_only_tools():
    tool_turn = SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", id="tu1", name="get_market_data", input={"symbol": "XAUUSD"})
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        model="claude-opus-5-5",
    )
    final = claude_text(
        {"summary": "s", "facts": ["f"], "calculations": [], "interpretation": ["i"], "uncertainty": ["u"]}
    )
    fake = FakeAnthropic([tool_turn, final])
    calls = []

    async def executor(name, args):
        calls.append((name, args))
        return {"summary": "quote", "facts": ["XAUUSD 2350"], "calculations": [], "data": {}}

    p = ClaudeProvider(ROUTER, None, client=fake)
    res, trace = await p.chat(
        "analyst_chat",
        [{"role": "user", "content": "gold?"}],
        TOOLS,
        executor,
        __import__("ai.schemas.outputs", fromlist=["ChatAnswer"]).ChatAnswer,
    )
    assert calls == [("get_market_data", {"symbol": "XAUUSD"})]
    assert trace[0].ok and res.data["facts"] == ["f"]
    second = fake.calls[1][1]["messages"]
    assert (
        second[-1]["content"][0]["type"] == "tool_result" and second[-1]["content"][0]["tool_use_id"] == "tu1"
    )
    with pytest.raises(AIProviderError) as exc:
        await p.chat(
            "analyst_chat",
            [],
            [ToolSpec(name="place_order", description="x", parameters={}, read_only=False)],
            executor,
            SignalAnalysis,
        )
    assert exc.value.code == "AI_TOOL_FORBIDDEN"


async def test_gemini_structured_and_validation():
    fake = FakeGemini([gemini_text(analysis("SHORT"))])
    p = GeminiProvider(ROUTER, None, client=fake)
    res = await p.analyze_signal(PAYLOAD)
    model, _, config = fake.calls[0]
    assert model == "gemini-3.1-pro-preview" and config.response_mime_type == "application/json"
    assert (
        res.data["direction"] == "SHORT" and res.usage.input_tokens == 500 and res.usage.output_tokens == 120
    )
    assert res.usage.cost_usd is None  # no hard-coded Gemini pricing
    assert (await p.validate()).status.value == "CONNECTED"
    assert (await GeminiProvider(ROUTER, None).validate()).status.value == "NOT_CONFIGURED"


def test_validation_flags_unsupported_prices_and_overconfidence():
    good = validate_signal_analysis(analysis(), PAYLOAD, 1.5)
    assert good.valid and not good.unsupported_prices
    bad = validate_signal_analysis(
        analysis(referenced_prices=[2412.5], reasoning=["This is a guaranteed winner"]), PAYLOAD, 1.5
    )
    codes = {i.code for i in bad.issues}
    assert not bad.valid and {"UNSUPPORTED_PRICE", "OVERCONFIDENCE"} <= codes
    low_rr = {**PAYLOAD, "quant": {"levels": {"effective_rr": 1.1}}}
    assert "BAD_RISK_REWARD" in {i.code for i in validate_signal_analysis(analysis(), low_rr, 1.5).issues}
    ev = {**PAYLOAD, "events": {"next_high_impact_minutes": 30}}
    assert "NEWS_RISK_IGNORED" in {i.code for i in validate_signal_analysis(analysis(), ev, 1.5).issues}
    hq = validate_signal_analysis(analysis(analysis_quality="HIGH"), PAYLOAD, 1.5)
    assert "QUALITY_OVERSTATED" in {i.code for i in hq.issues}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("LONG", "LONG", Agreement.HIGH),
        ("NO_TRADE", "NO_TRADE", Agreement.HIGH),
        ("LONG", "NO_TRADE", Agreement.LOW),
        ("LONG", "SHORT", Agreement.CONFLICT),
        ("LONG", None, Agreement.SINGLE),
        (None, None, Agreement.UNAVAILABLE),
    ],
)
def test_consensus_rules(a, b, expected):
    res = AIConsensusEngine().compare(
        {"claude": analysis(a) if a else None, "gemini": analysis(b) if b else None}, "LONG"
    )
    assert res.agreement == expected
    assert res.ai_opposes_quant == ("SHORT" in (a, b))


async def test_review_without_providers_does_not_change_quant_decision():
    orch = AIReviewOrchestrator(ClaudeProvider(ROUTER, None), GeminiProvider(ROUTER, None))
    review = await orch.review(PAYLOAD, "LONG", 1.5)
    assert review.claude.status == review.gemini.status == "NOT_CONFIGURED"
    assert review.consensus.agreement == Agreement.UNAVAILABLE and not review.downgrade_to_no_trade
    strict = AIReviewOrchestrator(
        ClaudeProvider(ROUTER, None), GeminiProvider(ROUTER, None), require_ai_review=True
    )
    assert (await strict.review(PAYLOAD, "LONG", 1.5)).downgrade_to_no_trade


async def test_review_downgrades_on_conflict_and_critic_rejection():
    approve = {
        "verdict": "approved",
        "reasons": ["ok"],
        "unsupported_claims": [],
        "missing_evidence": [],
        "contradictions": [],
        "overconfidence": [],
        "risk_reward_issues": [],
        "news_risk_issues": [],
        "data_problems": [],
    }
    claude = ClaudeProvider(
        ROUTER, None, client=FakeAnthropic([claude_text(analysis("LONG")), claude_text(approve)])
    )
    gemini = GeminiProvider(ROUTER, None, client=FakeGemini([gemini_text(analysis("SHORT"))]))
    review = await AIReviewOrchestrator(claude, gemini).review(PAYLOAD, "LONG", 1.5)
    assert review.consensus.agreement == Agreement.CONFLICT and review.downgrade_to_no_trade
    assert (
        review.critic.verdict.value == "rejected"
    )  # deterministic critic overrides the AI critic's approval

    claude2 = ClaudeProvider(
        ROUTER, None, client=FakeAnthropic([claude_text(analysis("LONG")), claude_text(approve)])
    )
    gemini2 = GeminiProvider(ROUTER, None, client=FakeGemini([gemini_text(analysis("LONG"))]))
    ok = await AIReviewOrchestrator(claude2, gemini2).review(PAYLOAD, "LONG", 1.5)
    assert ok.consensus.agreement == Agreement.HIGH and ok.critic.verdict.value == "approved"
    assert not ok.downgrade_to_no_trade and len(ok.usages()) == 3

    reject = {**approve, "verdict": "rejected", "reasons": ["Overstated"]}
    claude3 = ClaudeProvider(
        ROUTER, None, client=FakeAnthropic([claude_text(analysis("LONG")), claude_text(reject)])
    )
    gemini3 = GeminiProvider(ROUTER, None, client=FakeGemini([gemini_text(analysis("LONG"))]))
    rej = await AIReviewOrchestrator(claude3, gemini3).review(PAYLOAD, "LONG", 1.5)
    assert rej.downgrade_to_no_trade and "AI critic verdict: rejected" in rej.reasons


async def test_review_cannot_create_a_trade_from_no_trade():
    claude = ClaudeProvider(
        ROUTER,
        None,
        client=FakeAnthropic(
            [
                claude_text(analysis("LONG")),
                claude_text(
                    {
                        "verdict": "approved",
                        "reasons": [],
                        "unsupported_claims": [],
                        "missing_evidence": [],
                        "contradictions": [],
                        "overconfidence": [],
                        "risk_reward_issues": [],
                        "news_risk_issues": [],
                        "data_problems": [],
                    }
                ),
            ]
        ),
    )
    review = await AIReviewOrchestrator(claude, GeminiProvider(ROUTER, None)).review(PAYLOAD, "NO_TRADE", 1.5)
    assert not review.downgrade_to_no_trade and review.consensus.quant_direction == "NO_TRADE"


async def test_demo_fallback_is_labelled_and_refuses_model_tasks():
    demo = DemoRuleBasedProvider()
    with pytest.raises(AIProviderError):
        await demo.analyze_signal(PAYLOAD)
    res, _ = await BriefingWriter([]).write(
        {
            "assets": [
                {
                    "symbol": "XAUUSD",
                    "price": 2350,
                    "change_pct": 0.5,
                    "trend": "BULLISH",
                    "trend_score": 40,
                    "regime": "TRENDING_BULLISH",
                    "vol_percentile": 95,
                    "signal": "LONG",
                    "score": 70,
                }
            ],
            "events": [{"event": "US CPI", "currency": "USD", "impact": "HIGH", "time": "13:30"}],
            "is_demo": True,
        }
    )
    assert res.is_demo and res.provider == "rule-based"
    assert "no AI model" in res.data["interpretation"][0]
    assert any("US CPI" in r for r in res.data["major_risks"])
    exp, _ = await AIExplainer([]).explain({"symbol": "XAUUSD", "score": 70, "components": [], "levels": {}})
    assert "not a probability" in exp.data["calculations"][0]
    scan, raw = await AIChartAnalyzer([]).analyze(ImageInput(data=b"x", mime_type="image/png"), {})
    assert not scan.available and raw is None and "IMAGE ANALYSIS" in scan.label


async def test_rule_based_chat_uses_tools_transparently():
    calls = []

    async def executor(name, args):
        calls.append(name)
        return {
            "summary": f"{name} ok",
            "facts": [f"fact from {name}"],
            "calculations": [f"calc from {name}"],
            "data": {},
        }

    agent = AIChatAgent([], executor, lambda t: {"GOLD": "XAUUSD", "XAUUSD": "XAUUSD"}.get(t.upper()))
    resp = await agent.ask("What is happening with Gold? Compare historical setups")
    assert not resp.is_ai and resp.provider == "rule-based"
    assert calls[:3] == ["get_market_data", "get_indicators", "get_structure"]
    assert "get_historical_setups" in calls and all(t.ok for t in resp.tool_trace)
    assert resp.answer.facts and "no AI model" in resp.answer.interpretation[0]
    blocked = await agent._guarded("place_order", {})
    assert "error" in blocked
