# AI system

AI in NEXUS is an **independent reviewer and explainer**, never a decision maker.
It sees structured, already-computed data; its output is schema-validated and then
checked deterministically; it can only make a signal *more conservative*.

## Components (`services/ai`)

| Component | Role |
| --- | --- |
| `providers/base.py` | `AIProvider` abstraction: `analyze_market`, `analyze_signal`, `criticize_signal`, `summarize_market`, `analyze_chart`, `research_asset`, `classify_news` |
| `providers/claude/provider.py` | `ClaudeProvider` (Anthropic SDK): structured JSON output via `output_config` JSON schema, effort setting, refusal / max-tokens handling, optional server-side fallback model, manual tool loop |
| `providers/gemini/provider.py` | `GeminiProvider` (google-genai): `response_json_schema`, function declarations executed manually (automatic calling disabled) |
| `providers/demo.py` | Rule-based fallback; outputs are labelled non-AI and it refuses tasks it cannot do honestly (signal review, critic, image analysis) |
| `orchestration/router.py` | Model routing: *fast* models for chat/news/briefings, *strong* models for signal review, critic and research |
| `orchestration/analysts.py` | `AIReviewOrchestrator`: ClaudeAnalyst and GeminiAnalyst run independently and in parallel on the same input |
| `orchestration/consensus.py` | `AIConsensusEngine`: agreement HIGH / MEDIUM / LOW / CONFLICT / SINGLE / UNAVAILABLE |
| `critic/validation.py`, `critic/critic.py` | Deterministic validation + `AICritic` (approved / rejected / needs_more_data) |
| `orchestration/services.py` | `AIExplainer`, `AIResearcher`, `BriefingWriter`, `NewsClassifier`, `AIChartAnalyzer` |
| `orchestration/tools.py`, `chat.py` | Read-only tools and the analyst chat agent |
| `prompts/registry.py` | Versioned prompts |
| `schemas/outputs.py` | Strict output schemas (`additionalProperties: false`) |

## Independence and consensus

Gemini is never shown Claude's conclusion (and vice versa). Both return:

```json
{"direction": "LONG|SHORT|NO_TRADE", "reasoning": [], "supporting_factors": [],
 "opposing_factors": [], "key_risks": [], "invalidation": "",
 "analysis_quality": "LOW|MEDIUM|HIGH", "disagreements": [], "referenced_prices": []}
```

Consensus rules: same direction → HIGH (MEDIUM if either rates its own analysis LOW);
one directional and one NO_TRADE → LOW; LONG vs SHORT → CONFLICT; one valid → SINGLE;
none → UNAVAILABLE. With `block_on_low_agreement`, LOW/CONFLICT downgrade the signal.
Agreement is never presented as proof of correctness.

## Validation and critic

Every AI output is validated deterministically before use:
prices it cites must exist in the input (no invented levels), certainty language
("guaranteed", "risk-free"…) is flagged, R:R claims must be consistent, high-impact
news risk must be acknowledged, and "HIGH quality" claims on weak data are flagged.
The critic (AI review + the deterministic findings) checks unsupported claims,
missing evidence, contradictions, overconfidence, R:R and news-risk issues and data
problems. The most restrictive verdict wins. AI can downgrade a signal to NO_TRADE;
it can never upgrade one.

## Prompts

| Prompt | Version | Used for |
| --- | --- | --- |
| `signal_analysis` | 1.0.0 | Independent analyst review |
| `signal_critic` | 1.0.0 | Critic |
| `market_briefing` | 1.0.0 | Session briefings |
| `chart_image_analysis` | 1.0.0 | Screenshot analysis |
| `asset_research` | 1.0.0 | Research workspace |
| `news_sentiment` | 1.0.0 | Sentiment classification |
| `analyst_chat` | 1.0.0 | AI Analyst chat |
| `signal_explainer` | 1.0.0 | Explanations |

Each prompt has a name, version, date, task tier and settings; the version, model and
settings are stored with every AI analysis (`GET /api/ai/prompts`). All prompts share
grounding rules: use only supplied data, never invent prices/news/events, separate
FACTS / CALCULATIONS / INTERPRETATION / UNCERTAINTY, no certainty language.

## Tools (chat and research)

Read-only, allow-listed, executed by NEXUS, never by the model:
`get_market_data`, `get_indicators`, `get_structure`, `get_news`, `get_calendar`,
`get_historical_setups`, `get_portfolio`, `get_risk_status`, `calculate_signal`,
`calculate_position_size` (a calculation, not an order). There is no order tool.
The UI shows every tool call and result summary.

## Cost control

Model routing (fast vs. strong), a response cache (`cache_minutes`), a daily call cap
(`max_calls_per_day`), per-minute rate limits and AI only on candidate setups (the
scanner never calls AI). Token usage, latency and cost estimates are stored in
`ai_calls` and shown on Analytics → AI model analytics. Claude list prices are built in;
other models need `AI_PRICING_JSON` or show "n/a".

## Without keys

The rule-based provider produces labelled non-AI briefings, explanations and chat
answers from the same tools. Signal AI review shows UNAVAILABLE; image analysis is
unavailable. Nothing is presented as AI output when no model ran.
