# LLM Providers and Models

This page lists all providers and models configured in `config/tools/llms.yaml`.

`llms.yaml` is a **generated file**: the source of truth is the shared model
registry `models.yaml` in the sibling `my-dev-team-config` repository, which
also generates the model catalogue of `my-dev-team-vs-code`. To add or change
a model, edit the registry there and run `python scripts/sync_models.py` - see
that repo's README for the schema. Never edit `llms.yaml` by hand. A committed
pre-commit hook (`.githooks/pre-commit`, activate once with
`git config core.hooksPath .githooks`) blocks commits while the generated file
is stale; it skips silently on machines without the config checkout.

The **Verified** column is updated manually when integration tests pass for that model. A blank cell means the model has not yet been tested end-to-end.

---

## How providers are selected

Pass `--provider <name>` on the CLI (or set `provider:` in `config.yaml`). The factory scores every model in that provider's list against the agent's declared capabilities and picks the highest scorer. See [Configuration](config.md) for persistent defaults.

---

## Complexity-aware routing

Capabilities describe *what kind of work* an agent does (reasoning, code generation). Complexity describes *how much horsepower* a specific task needs. Both dimensions feed into model selection, so the same agent can run on a cheap model for a trivial task and a strong model for a hard one.

### Where complexity comes from

Two agents produce complexity signals during the planning phase:

- **Product Manager** - assesses the whole project and emits `project_complexity` (`low` / `medium` / `high`) alongside the Technical Specifications. Stored on `state.project_complexity`.
- **System Architect** - assigns a `complexity` to every task in the backlog. The officer node carries it into `TaskContext.current_task_complexity` when dispatching the task.

Both levels use the same three-value scale:

| Value | Meaning |
|---|---|
| `low` | Small, well-understood scope, clear requirements, trivial logic |
| `medium` | Moderate scope, some design decisions, non-trivial integration |
| `high` | Large scope, significant architectural complexity, novel algorithms, substantial ambiguity |

### How agents consume it

Routing is **opt-in per agent**. Add `complexity_routing: true` to the agent's frontmatter:

```yaml
---
role: Senior Developer
capabilities: [code-generation]
complexity_routing: true
---
```

When enabled, `BaseAgent` reads `state.task_context.current_task_complexity` (falling back to `state.project_complexity`) and passes it to the factory on every call. Chains are cached per complexity level, so a single agent instance may hold multiple bound LLMs - one per distinct complexity seen during the run.

Currently enabled on: `senior-developer`, `system-architect`. Other agents (code reviewer, QA, judge) stay pinned to capability-only scoring by default.

Pass `--no-complexity-routing` on the CLI (or set `no_complexity_routing: true` in `config.yaml`) to globally disable routing for all agents regardless of their frontmatter - model selection falls back to capability scoring only.

### How the factory scores

Each model in `llms.yaml` may declare a `complexity_fit` block:

```yaml
- id: 'claude-opus-4-8'
  capabilities:
      reasoning: 0.98
      code-generation: 0.97
      code-analysis: 0.97
      planning: 0.97
  complexity_fit: {low: 0.3, medium: 0.8, high: 1.0}
```

The selection formula becomes:

```
score = weighted_capability_score * complexity_fit[complexity]
```

When `complexity_fit` is missing, the multiplier defaults to `1.0` (neutral). When the agent does not route on complexity, the multiplier is not applied at all.

The multiplication is intentional. A fast model that scores 1.0 on `code-generation` but has `complexity_fit.high = 0.2` loses to a larger model with `code-generation = 0.9` and `complexity_fit.high = 1.0` on high-complexity tasks - but wins on low-complexity ones where the roles reverse. This naturally biases selection toward cheap/fast models for trivial work and strong models for hard work without manual per-agent overrides.

### Per-complexity parameter overrides

Agents can also tune parameters per complexity level via `complexity_overrides`:

```yaml
---
role: System Architect
capabilities: [planning, reasoning]
temperature: 0.1
complexity_routing: true
complexity_overrides:
  high: {temperature: 0.3, thinking: true}
  low:  {temperature: 0.1}
---
```

Supported override keys:
- `temperature` - replaces the base temperature for calls at this complexity
- `thinking` - for Ollama models, overrides the model-level `thinking:` default (enables or disables the reasoning stream)

### Telemetry

When complexity routing kicks in, `BaseAgent.process()` logs `Routing on complexity=<level>` at INFO. The underlying LangChain `node:<name>` tag on the LLM is unchanged, so existing tracing still works - complexity just affects *which* model gets tagged.

---

## Per-model prompt steering

The agent prompts assume a capable model; a weaker model needs extra nudging to hit the same bar. Rather than fork prompts per model, `utils/steering.py` (ported from my-dev-team-vs-code's `engine/config/steering.ts`) derives a small "Model-specific guidance" section from the routed model's capability scores in `llms.yaml` and appends it to the agent's system prompt. Each rule fires only when the model scores **below** its threshold:

| Capability | Below | Guidance |
|---|---|---|
| `structured-output` | 0.9 | submit the result as a single tool call, no plain-text JSON or prose around it |
| `reasoning` | 0.8 | work step by step, do not guess at unproven conclusions |
| `code-generation` | 0.85 | never invent paths/APIs/identifiers - verify with a tool |

A frontier model (Opus, GPT-5.5, Gemini Pro) clears every threshold and gets nothing - its prompt is byte-identical to before. A small local model (qwen3:8b, gemma3:4b) collects most of the lines. A missing score counts as 0, so an unscored model gets the full set. No per-model configuration is involved: a newly registered model is steered automatically from its registry scores, and the section follows complexity routing (the low-complexity chain of an agent may be steered while its high-complexity chain is not). Fired rules are logged at DEBUG per node and model.

---

## Structured-output self-repair

Steering reduces malformed output up front; self-repair handles what still slips through. When a submitted tool call fails validation against the agent's output schema (a missing required field, a wrong type), `BaseAgent` re-asks the same model with the *actual* validation errors appended to the conversation - the failing field paths and their messages, plus an order to re-emit only the corrected tool call, no commentary (ported from my-dev-team-vs-code's `repair.ts`). A response with no tool call at all keeps getting the generic "you must call one of the available tools" reminder. Both repair paths ride the existing retry loop, so attempts stay bounded by `max_retries` (2 extra attempts); a failure that survives every attempt fails the step exactly as before.

Each corrective re-ask is a real, billed model call, so it is metered: the call carries a `repaired` run tag that `TelemetryTracker` counts. The final receipt prints a "Repaired Calls" row, each call record carries a `repaired` flag, and the optimization report flags agents whose calls needed repair ("Output Repair": repaired vs. total calls). Watch that number when swapping models or editing prompts - a rising repair rate means the model needs the steering or a stronger registry entry, and every repair doubles that step's prompt cost.

---

## anthropic

**Package:** `pip install "my-dev-team[anthropic]"`
**Env var:** `ANTHROPIC_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `claude-opus-4-8` | reasoning, planning, code | |
| `claude-sonnet-4-6` | planning, code generation, code analysis | |
| `claude-haiku-4-5-20251001` | fast utility tasks | |

---

## azure-anthropic

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)
**Env vars:** `AZURE_ANTHROPIC_ENDPOINT`, `AZURE_ANTHROPIC_API_KEY`

```
AZURE_ANTHROPIC_ENDPOINT=https://your-resource.services.ai.azure.com/models
AZURE_ANTHROPIC_API_KEY=your_key_here
```

Claude models deployed via Azure AI Foundry expose an OpenAI-compatible REST API. The endpoint URL is available in the Azure AI Foundry portal under your model deployment.

| Model | Best for | Verified |
|---|---|---|
| `claude-opus-4-8` | reasoning, planning, code | |
| `claude-sonnet-4-6` | planning, code generation, code analysis | |
| `claude-haiku-4-5-20251001` | fast utility tasks | |

---

## azure-openai

**Package:** `pip install "my-dev-team[openai]"`
**Env vars:** `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your_key_here
```

By default the deployment name is assumed to match the model `id` in `llms.yaml`. If your Azure deployment has a different name, set `AZURE_OPENAI_DEPLOYMENT` to override it for all models. The API version defaults to `2024-08-01-preview` and can be overridden with `AZURE_OPENAI_API_VERSION`.

| Model | Best for | Verified |
|---|---|---|
| `gpt-5.5` | reasoning, planning, code | |
| `gpt-5.4-mini` | fast utility tasks | |

---

## openai

**Package:** `pip install "my-dev-team[openai]"`
**Env var:** `OPENAI_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `gpt-5.5` | reasoning, planning | |
| `gpt-5.1-codex-mini` | code generation, code analysis | |
| `gpt-4.1` | planning, code generation | |
| `gpt-4.1-mini` | fast utility tasks | |

---

## groq

**Package:** `pip install "my-dev-team[groq]"`
**Env var:** `GROQ_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `qwen/qwen3-32b` | reasoning | 2026-03-28 |
| `openai/gpt-oss-120b` | planning, code generation, code analysis | 2026-03-28 |
| `llama-3.1-8b-instant` | fast utility tasks | 2026-03-28 |

---

## ollama

**Package:** `pip install "my-dev-team[ollama]"`
**Env var:** none (local service)
**Guide:** [Ollama setup](ollama.md)

Models with `thinking: true` in `llms.yaml` have the reasoning stream enabled (requires `--thinking`).

| Model | Thinking | Best for | Verified |
|---|---|---|---|
| `qwen3:8b` | yes | classification, structured output, fast utility tasks | 2026-03-28 |
| `qwen3:14b` | yes | reasoning, planning | |
| `qwen3-coder:30b` | no | code generation, code analysis, long context | |
| `gemma3:4b` | no | fast utility tasks | 2026-03-28 |

Note: `qwen2.5-coder:7b` was retired from the registry in favour of
`qwen3-coder:30b` when the model lists of the two apps were reconciled.

---

## google

**Package:** `pip install "my-dev-team[google]"`
**Env var:** `GOOGLE_API_KEY`

LangChain reports this provider as `google_genai`. The alias `'google_genai/*': 'gemini/*'` in `llms.yaml` maps it to the correct litellm prefix for cost tracking.

| Model | Best for | Verified |
|---|---|---|
| `gemini-3.1-pro-preview` | reasoning, planning, code, long context | |
| `gemini-3.5-flash` | balanced all-round work, long context | |
| `gemini-3.1-flash-lite` | fast utility tasks | |

---

## mistral

**Package:** `pip install "my-dev-team[mistral]"`
**Env var:** `MISTRAL_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `mistral-medium-latest` | planning, code generation, code analysis | |
| `codestral-latest` | code generation, code analysis | |
| `mistral-small-latest` | fast utility tasks | |

---

## deepseek

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)
**Env var:** `DEEPSEEK_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `deepseek-v4-pro` | reasoning, planning | |
| `deepseek-v4-flash` | planning, code generation, code analysis | |

---

## zai

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)
**Env var:** `ZAI_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `glm-5.2` | reasoning, planning, code | |
| `glm-4.7-flash` | fast utility tasks | |

---

## grok

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)
**Env var:** `XAI_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `grok-4.3` | reasoning, planning, code | |
| `grok-4.1-fast` | planning, code generation, code analysis | |
| `grok-code-fast-1` | fast utility tasks | |

---

## free (compound)

No API key required for cloud models when Groq free-tier limits apply. Ollama models run locally.

The `free` provider is a compound provider - each model entry carries a `provider` field pointing to its real backend (`groq` or `ollama`). No separate install is needed beyond those two. Rate limiting is charged to the real backend: the Groq models draw from Groq's per-provider budget (30 RPM registry default) while the local Ollama calls stay unthrottled.

| Model | Backend | Best for |
|---|---|---|
| `qwen/qwen3-32b` | groq | balanced all-round work |
| `openai/gpt-oss-120b` | groq | reasoning, planning, code |
| `llama-3.1-8b-instant` | groq | fast utility tasks |
| `qwen3-coder:30b` | ollama | code generation, code analysis |

---

## Rate limiting and 429 retries

Requests are throttled per provider with rolling one-minute windows (`utils/rate_limiter.py`, behavior ported from my-dev-team-vs-code's `rateLimiter.ts`). A provider's budget resolves as: the `--rpm` flag when set (> 0, then it applies to every provider), else the provider's default from the shared registry (the `rpm` key of its `llms.yaml` section - currently only Groq seeds one, 30 RPM for the free tier), else no throttle. Budgets are keyed by the routed model's real backend, so a compound provider like `free` never spends the Groq budget on its local Ollama calls.

Independently of throttling, a rate-limited call (HTTP 429) is retried automatically: the delay comes from the response's `retry-after-ms`/`retry-after` headers or the provider's "try again in Ns" message hint (Groq phrases its limit this way), falling back to exponential backoff - up to 5 attempts, each wait capped at 60 seconds. A 429 that persists past the cap fails the step like before, where checkpoint resume still applies.

## Adding models

`llms.yaml` is generated - do not edit it by hand. To add a model, add an entry to `models.yaml` in the `my-dev-team-config` repository (unified capability scores plus a `complexity_fit` block, see that repo's README) and run `python scripts/sync_models.py` there. Then add a row to the table above with an empty Verified cell. Mark Verified once integration tests confirm the model works end-to-end with the full agent workflow.

To add an entirely new provider, add a `case` block in `LLMFactory._instantiate()` in `src/devteam/utils/llm_factory.py`, add the provider to `DEVTEAM_PROVIDERS` in the sync script, and add a new section on this page.
