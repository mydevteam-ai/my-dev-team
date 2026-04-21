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

The entire workflow is a cyclic LangGraph state machine. A manager class (in `managers/`) builds the graph and acts as the central router. All managers extend `BaseManager`, which owns the graph structure, error handling and phase dispatch skeleton. Subclasses implement `_planning_node` and `_route_planning` for their specific workflow.

Two workflows are currently available, selected via `--workflow`:

**`development` (default)** - `ProjectManager` = `BaseManager` + `PlanningManager`:
- `planning` - PM refines requirements, Architect creates task backlog
- `development` - Developer/Reviewer/QA loop per task
- `integration` - Final QA then Reporter

**Fan-out mode** (activated via `--fanout` flag or by appending `-fanout` to any workflow name, e.g. `--workflow development-fanout` or `--workflow migration-fanout`) - replaces the single Developer with a fan-out-fan-in pattern applied at runtime by `AgentsFactory.fanout_transform()`. No separate YAML file is needed; the transform works for any workflow:
- Two `SeniorDeveloper` instances (`developer_a`, `developer_b`) are injected - `developer_b` gets `reasoning: 1.0` added to the base developer's capabilities
- `CodeJudge` (`judge` node) compares both drafts and selects the winner
- All subsequent revisions (after code review or QA rejection) use the winning developer only

**`migration`** - `MigrationManager` extends `BaseManager`:
- `planning` - CodeAnalyzer reads source workspace, produces Migration Analysis and task backlog
- `development` - Migrator translates source units, EquivalenceChecker validates behavioral equivalence
- `integration` - Final QA then Reporter

The `officer` node dispatches tasks by finding those whose dependencies are all complete and fanning them out as independent parallel `Send()` branches. Each branch runs its own full dev→review→qa cycle.

### State (`state/project_state.py`)

`ProjectState` is a Pydantic `BaseModel` used as the LangGraph state. Fields use LangGraph reducer annotations to handle concurrent writes from parallel branches:
- `Annotated[X, _last_value]` - last write wins (for scalars like `current_phase`)
- `Annotated[dict, _merge_workspace_files]` - dict merge (for concurrent file writes)
- `Annotated[list, operator.add]` - list accumulation (for `communication_log`, etc.)

### Agent Factory Chain

```
CLI (--provider, --workflow flags)
  → LLMFactory(provider)
    → CrewFactory
      → AgentsFactory  [reads config/crews/{workflow}.yaml]
        → crew YAML: manager: field  →  ManagerClass resolved via getattr(devteam.managers, ...)
        → AgentClass.from_config(node_name, config_file)
          → parses config/agents/{file}.md  [YAML frontmatter + prompt]
            → BaseAgent.__init__(config, prompt, node_name, llm_factory)
```

At call time, `BaseAgent._get_chain(complexity)` calls `llm_factory.create(capabilities, temperature, complexity=...)` which scores all models in `config/tools/llms.yaml` and returns the best-fit provider-specific LangChain chat model with tools bound. Chains are cached per complexity level on the agent instance.

### Agent Base Class (`agents/base_agent.py`)

`BaseAgent[T]` is generic over its output schema. Subclasses declare:
- `output_schema: type[T]` - Pydantic model for the structured result
- `tools: list[type[BaseModel]]` - tool schemas passed to `bind_tools()`
- Override `_map_tool_to_output()`, `_update_state()`, `_pre_process()`, `_post_process()` as needed

`process()` always injects `messages` from `state.messages` - do not declare it in `inputs:`. `_build_inputs` handles five other special keys automatically:
- `skills` - loads and formats the full skills catalog
- `skills_context` - loads the skills catalog and ranks entries by relevance to the current task via BM25; top skills are shown in full, the rest are listed as names (use for agents that use `LoadSkill` to fetch skill bodies on demand)
- `workspace` - reads all file contents from `state.workspace_path` (full text; use for agents that need pre-loaded content, e.g. Reporter)
- `workspace_listing` - injects only file paths, not content (use for agents that will read files via tools, e.g. CodeAnalyzer)
- `workspace_context` - ranks workspace files by BM25 relevance to the current task; top files are shown in full, the rest are listed as paths (use for task-scoped agents that also have `ReadFile` / `GlobFiles` / `GrepFiles` tools, e.g. QA Engineer, Migrator)

The `process()` loop invokes the LLM, then calls `_coerce_tool_calls()` to handle models that emit tool calls as plain-text JSON instead of native function calls (common with smaller Ollama models). If no tool call is found after coercion, it retries with an injected reminder message.

### LLM Routing (`utils/llm_factory.py` + `config/tools/llms.yaml`)

Agents declare `capabilities` in their `.md` frontmatter - either a list (equal weights) or a weighted dict. `LLMFactory._select_model()` scores every model in `config/tools/llms.yaml` by computing a weighted sum of capability scores and returns the highest scorer.

**Complexity-aware routing.** Agents can opt in with `complexity_routing: true` in their frontmatter. When enabled, `BaseAgent` reads complexity from `state.task_context.current_task_complexity` (falling back to `state.project_complexity`) and passes it to the factory. Each model in `llms.yaml` declares `complexity_fit: {low, medium, high}` which multiplies the capability score, biasing selection toward models appropriate for the task's difficulty. Complexity signals originate from the Product Manager (project-level, `ProductManagerResponse.project_complexity`) and the System Architect (per-task, `DevelopmentTask.complexity`). Agents can also declare `complexity_overrides:` to tune `temperature` or ollama `thinking` per complexity level.

Ollama models additionally require a `thinking: true/false` field; only models with `thinking: true` have the `reasoning` stream enabled. This can be overridden per-call via the `thinking` kwarg on `LLMFactory.create()`.

**Compound providers** are pseudo-providers defined in `config/tools/llms.yaml` under `providers:` like any other, but each model entry carries a `provider:` field pointing to the real backend. The factory reads `model.get('provider', self.provider)` and dispatches to the correct `_instantiate()` branch. The built-in `free` compound provider combines Groq free-tier models with local Ollama models. Add new compound providers by adding a new key under `providers:` with per-model `provider:` fields — no factory changes needed.

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
