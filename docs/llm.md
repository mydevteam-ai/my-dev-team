# LLM Providers and Models

This page lists all providers and models configured in `config/tools/llms.yaml`.

The **Verified** column is updated manually when integration tests pass for that model. A blank cell means the model has not yet been tested end-to-end.

---

## How providers are selected

Pass `--provider <name>` on the CLI (or set `provider:` in `config.yaml`). The factory scores every model in that provider's list against the agent's declared capabilities and picks the highest scorer. See [Configuration](config.md) for persistent defaults.

---

## anthropic

**Package:** `pip install "my-dev-team[anthropic]"`  
**Env var:** `ANTHROPIC_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `claude-opus-4-6` | reasoning, planning, code | |
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
| `claude-opus-4-6` | reasoning, planning, code | |
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
| `gpt-5.3-codex` | code generation, code analysis | |
| `gpt-5.4-mini` | fast utility tasks | |

---

## openai

**Package:** `pip install "my-dev-team[openai]"`  
**Env var:** `OPENAI_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `o3` | reasoning, planning | |
| `codex-mini-latest` | code generation, code analysis | |
| `gpt-4.1` | planning, code generation | |
| `gpt-4.1-mini` | fast utility tasks | |

---

## groq

**Package:** `pip install "my-dev-team[groq]"`  
**Env var:** `GROQ_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `qwen/qwen3-32b` | reasoning | |
| `openai/gpt-oss-120b` | planning, code generation, code analysis | |
| `llama-3.1-8b-instant` | fast utility tasks | |

---

## ollama

**Package:** `pip install "my-dev-team[ollama]"`  
**Env var:** none (local service)  
**Guide:** [Ollama setup](ollama.md)

Models with `thinking: true` in `llms.yaml` have the reasoning stream enabled (requires `--thinking`).

| Model | Thinking | Best for | Verified |
|---|---|---|---|
| `qwen3:8b` | yes | reasoning | |
| `qwen2.5-coder:7b` | no | planning, code generation, code analysis | |
| `gemma3:4b` | no | fast utility tasks | |

---

## google

**Package:** `pip install "my-dev-team[google]"`  
**Env var:** `GOOGLE_API_KEY`

LangChain reports this provider as `google_genai`. The alias `'google_genai/*': 'gemini/*'` in `llms.yaml` maps it to the correct litellm prefix for cost tracking.

| Model | Best for | Verified |
|---|---|---|
| `gemini-3.1-flash-lite-preview` | fast utility tasks | 2026-04-12 |
| `gemini-3.1-pro-preview` | reasoning, planning, code | |

Note: `gemini-3.1-pro-preview` is commented out in `llms.yaml` by default. Uncomment to enable it.

---

## mistral

**Package:** `pip install "my-dev-team[mistral]"`  
**Env var:** `MISTRAL_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `mistral-large-latest` | planning, code generation, code analysis | |
| `codestral-latest` | code generation, code analysis | |
| `mistral-small-latest` | fast utility tasks | |

---

## deepseek

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)  
**Env var:** `DEEPSEEK_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `deepseek-reasoner` | reasoning, planning | |
| `deepseek-chat` | planning, code generation, code analysis | |

---

## grok

**Package:** `pip install "my-dev-team[openai]"` (uses OpenAI-compatible client)  
**Env var:** `XAI_API_KEY`

| Model | Best for | Verified |
|---|---|---|
| `grok-3` | reasoning, planning, code | |
| `grok-3-fast` | planning, code generation, code analysis | |
| `grok-3-mini-fast` | fast utility tasks | |

---

## free (compound)

No API key required for cloud models when Groq free-tier limits apply. Ollama models run locally.

The `free` provider is a compound provider - each model entry carries a `provider` field pointing to its real backend (`groq` or `ollama`). No separate install is needed beyond those two.

| Model | Backend | Best for | Verified |
|---|---|---|---|
| `qwen/qwen3-32b` | groq | reasoning | |
| `openai/gpt-oss-120b` | groq | planning, code generation, code analysis | |
| `llama-3.1-8b-instant` | groq | fast utility tasks | |
| `qwen2.5-coder:7b` | ollama | code generation, code analysis | |

---

## Adding models

To add a model, append an entry under the relevant provider in `config/tools/llms.yaml` and then add a row to the table above with an empty Verified cell. Mark Verified once integration tests confirm the model works end-to-end with the full agent workflow.

To add an entirely new provider, add a `case` block in `LLMFactory._instantiate()` in `src/devteam/utils/llm_factory.py` and a new section on this page.
