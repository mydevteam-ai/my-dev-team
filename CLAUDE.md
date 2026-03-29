# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
# Install in development mode
pip install -e .

# Run all tests
pytest

# Run a single test
pytest tests/test_agents.py::TestCodeReviewer::test_build_inputs -v

# Run tests matching a pattern
pytest -k "test_build_inputs"

# Lint
pylint src/devteam

# Run CLI
devteam project.txt --provider ollama

# Run web dashboard (requires pip install streamlit)
devteam-ui
```

## Architecture

### State Machine (LangGraph)

The entire workflow is a cyclic LangGraph state machine. `ProjectManager` (in `managers/`) builds the graph and acts as the central router. It is composed via mixins - `PlanningManager`, `ExecutionManager`, and `IntegrationManager` - each contributing node logic and routing for their respective phase.

The graph has three phases stored in `ProjectState.current_phase`:
- `planning` - PM refines requirements, Architect creates task backlog
- `development` - Developer/Reviewer/QA loop, runs in parallel fan-out via LangGraph `Send` API
- `integration` - Final QA then Reporter

The `officer` node dispatches tasks by finding those whose dependencies are all complete and fanning them out as independent parallel `Send()` branches. Each branch runs its own full dev→review→qa cycle.

### State (`state/project_state.py`)

`ProjectState` is a Pydantic `BaseModel` used as the LangGraph state. Fields use LangGraph reducer annotations to handle concurrent writes from parallel branches:
- `Annotated[X, _last_value]` - last write wins (for scalars like `current_phase`)
- `Annotated[dict, _merge_workspace_files]` - dict merge (for concurrent file writes)
- `Annotated[list, operator.add]` - list accumulation (for `communication_log`, etc.)

### Agent Factory Chain

```
CLI (--provider flag)
  → LLMFactory(provider)
    → CrewFactory
      → AgentsFactory  [reads config/crews/basic.yaml]
        → AgentClass.from_config(node_name, config_file)
          → parses config/agents/{file}.md  [YAML frontmatter + prompt]
            → BaseAgent.__init__(config, prompt, node_name, llm_factory)
```

At call time, `BaseAgent._llm` (a `@cached_property`) calls `llm_factory.create(capabilities, temperature)` which scores all models in `config/llms.yaml` and returns the best-fit provider-specific LangChain chat model with tools bound.

### Agent Base Class (`agents/base_agent.py`)

`BaseAgent[T]` is generic over its output schema. Subclasses declare:
- `output_schema: type[T]` - Pydantic model for the structured result
- `tools: list[type[BaseModel]]` - tool schemas passed to `bind_tools()`
- Override `_map_tool_to_output()`, `_update_state()`, `_pre_process()`, `_post_process()` as needed

The `process()` loop invokes the LLM, then calls `_coerce_tool_calls()` to handle models that emit tool calls as plain-text JSON instead of native function calls (common with smaller Ollama models). If no tool call is found after coercion, it retries with an injected reminder message.

### LLM Routing (`utils/llm_factory.py` + `config/llms.yaml`)

Agents declare `capabilities` in their `.md` frontmatter - either a list (equal weights) or a weighted dict. `LLMFactory._select_model()` scores every model in `llms.yaml` by computing a weighted sum of capability scores and returns the highest scorer.

Ollama models additionally require a `thinking: true/false` field; only models with `thinking: true` have the `reasoning` stream enabled.

**Compound providers** are pseudo-providers defined in `llms.yaml` under `providers:` like any other, but each model entry carries a `provider:` field pointing to the real backend. The factory reads `model.get('provider', self.provider)` and dispatches to the correct `_instantiate()` branch. The built-in `free` compound provider combines Groq free-tier models with local Ollama models. Add new compound providers by adding a new key under `providers:` with per-model `provider:` fields — no factory changes needed.

### Agent Config Format (`config/agents/*.md`)

Each agent is defined as a Markdown file with YAML frontmatter:

```
---
role: Senior Developer
capabilities: [code-generation]
temperature: 0.1
inputs: ['specs', 'current_task', 'workspace', 'skills', 'messages']
outputs: ['messages']
---
# Prompt template here...
```

`inputs` controls which `ProjectState` fields are injected into the prompt. `outputs` controls which fields are written back to state.

### Extensions

`VirtualCrew` supports lifecycle extensions implementing `on_start`, `on_step`, `on_pause`, `on_finish`. Extensions are passed to `crew_factory.create()` and can return state update dicts or set `abort_requested`. Built-in: `ConsoleLogger`, `HumanInTheLoop`, `GitCommitter`.

### Settings (`settings.py`)

Global mutable settings (`llm_streaming`, `llm_timeout`, `workspace_dir`, `config_dir`) are module-level private variables exposed through getter/setter functions. The config dir defaults to the bundled `src/devteam/config/` but can be overridden via `--config` CLI flag.
