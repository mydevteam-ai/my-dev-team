# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.12.0] - 2026-04-12

### 🚀 Added

* **User config file (`config.yaml`):** Persistent defaults for all CLI flags can now be set in `./config.yaml` (project-level) or `~/.devteam/config.yaml` (global). Project-level overrides global; CLI flags override both. Pass `--settings <path>` to point to a different file.

* **Lazy workspace loading for Developer:** The Senior Developer agent no longer receives full file contents in its initial prompt. Instead, it receives a file listing and uses `ReadFile`, `GlobFiles` and `GrepFiles` tools to read only the files relevant to the current task.

* **Migration workflow (`--workflow migration`):** A new workflow mode for migrating existing codebases to a different language (e.g. COBOL to Java, PL/SQL to Python). Activated via the `--workflow` CLI flag.

* **`CodeAnalyzer` agent:** Reads the source workspace, identifies structure and business logic, and outputs a `MigrationAnalysisResponse` - a full Migration Analysis document plus a parallel task backlog with one task per source unit.

* **`Migrator` agent:** Translates individual source units to the target language, guided by the Migration Analysis. Produces idiomatic target-language code and equivalence tests for each translated unit.

* **`EquivalenceChecker` agent:** Verifies that migrated code is behaviorally equivalent to the original, checking every branch, edge case and mapping decision defined in the Migration Analysis.

* **`BaseManager` base class:** Extracted the shared graph-building, error-handling and phase-dispatch skeleton from `ProjectManager` into `BaseManager`. New managers only need to implement `_planning_node` and `_route_planning`.

* **Azure OpenAI provider (`--provider azure-openai`):** Added `azure-openai` as a standalone provider backed by `AzureChatOpenAI` from `langchain-openai`. The deployment name defaults to the model `id` and can be overridden with `AZURE_OPENAI_DEPLOYMENT`. API version defaults to `2024-08-01-preview` and can be overridden with `AZURE_OPENAI_API_VERSION`. Requires `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`.

* **Azure Anthropic Claude provider (`--provider azure-anthropic`):** Added `azure-anthropic` for Anthropic Claude 4.6 models deployed via Azure AI Foundry. Uses the OpenAI-compatible inference endpoint exposed by Azure AI Foundry. Includes `claude-opus-4-6`, `claude-sonnet-4-6` and `claude-haiku-4-5-20251001`. Requires `AZURE_ANTHROPIC_ENDPOINT` and `AZURE_ANTHROPIC_API_KEY`.

### 🐛 Fixed

* **`coerce_tool_calls` crashes on Gemini list-format content:** Google Gemini returns `AIMessage.content` as a list of typed blocks (`[{'type': 'text', 'text': '...', 'extras': {...}}]`) when extended thinking is active. `coerce_tool_calls` in `tools/extractor.py` passed this list directly to `_unwrap_fences`, which expected a string, causing a `TypeError`. A new `_extract_text` helper normalises list-of-blocks content to a plain string before processing. Verified with `gemini-3.1-flash-lite-preview` on 2026-04-12.

* **`Reporter` agent returns plain text instead of calling `SubmitReport`:** The reporter prompt gave no explicit instruction to use the `SubmitReport` tool, so the model wrote the report as a plain-text response and exhausted all retries. Added "call `SubmitReport` with the complete Markdown text" to the agent prompt in `config/agents/reporter.md`.

### ⚙️ Changed

* **`messages` injected automatically in `BaseAgent.process()`:** `messages` from `state.messages` is now always added to the LLM input dict after `_build_inputs`, regardless of whether the agent declares `messages` in its `inputs:` frontmatter. The `messages` switch-case branch has been removed from `_build_inputs`. All agent config files updated to remove the now-redundant `messages` entry from their `inputs:` lists.

* **TelemetryTracker cost resolution uses YAML aliases with wildcard support:** Aliases are read from the existing `aliases:` block in `config/tools/llms.yaml`. Added `'google_genai/*': 'gemini/*'` and `'google_vertexai/*': 'vertex_ai/*'` entries so all Google models resolve to the correct litellm prefix for cost tracking. The `groq/compound` alias for cost normalisation is also defined there.

* **`--history` takes a thread ID directly:** `--history <thread_id>` now works as a standalone command without requiring `--resume`. The old `--resume <id> --history` pattern is no longer needed.

* **`BaseAgent._build_inputs` handles `workspace` natively:** Agents that declare `workspace` in their `inputs:` frontmatter now get the full workspace content injected automatically, without needing to override `_build_inputs`. Removed redundant overrides from `FinalQAEngineer` and `CodeAnalyzer`.

* **`AgentsFactory` exposes `load_crew_config` and `create_agents_from_config`:** Allows callers (e.g. `CrewFactory`) to load a crew config once and pass it to both manager resolution and agent instantiation, avoiding a double YAML parse.

* **`ProjectManager` simplified:** Now a minimal two-mixin class (`BaseManager` + `PlanningManager`) with no duplicated logic.

* **Skills directory:** Removed all built-in skills from the package configuration. By default, the app now searches for a `skills` sub-folder in the current working directory. This location can be overridden using the `--skills` CLI argument.

### 🔧 Internal

* **`TaskContext` state isolation:** Extracted all per-task fields from `ProjectState` into a new `TaskContext` Pydantic model. `ProjectState` now holds a single `task_context: TaskContext` field. This separation prepares the state model for future parallel task execution, where each task branch owns its own isolated context.

* **Agent inputs delivered as a HumanMessage:** `BaseAgent._build_prompt` now auto-generates a `HumanMessagePromptTemplate` from the agent's declared `inputs:` frontmatter keys, rendering each as an XML-tagged section. `_build_inputs` returns a flat kwargs dict; LangChain handles substitution at invocation time. System prompts are now pure instruction text. Extra runtime inputs (`drafts` in `CodeJudge`, `history` in `Reporter`) are declared in the frontmatter and populated by `_build_inputs` overrides - no `_data_input_keys` override needed. This also fixes compatibility with providers (Google Gemini) that reject requests with no user turn. `StreamHandler.on_llm_new_token` now skips non-string tokens emitted by Gemini for tool-call chunks.

## [0.11.6] - 2026-04-07

### 🚀 Added

* **Workspace hydrating (`--seed`):** Pass an existing local directory or `.zip` archive to pre-populate the workspace before agents run.

## [0.11.5] - 2026-04-07

### 🚀 Added

* **Provider optional dependency groups:** Each LLM provider now has its own extras group - `anthropic`, `google`, `groq`, `mistral`, `ollama` and `openai`. Install only what you need: `pip install "my-dev-team[groq,ollama]"`.

* **`rag` optional dependency group:** `pip install "my-dev-team[rag]"` now installs both `mcp` (agent context retrieval) and `vectorize-me` (document ingestion CLI).

### 🗑️ Removed

* **`mcp-ingest` CLI removed from `my-dev-team`:** Document ingestion is now provided by the standalone `vectorize-me` package, installed via `pip install "my-dev-team[rag]"`. The `mcp-ingest` command is unchanged - only its source location has moved.

## [0.11.4] - 2026-04-06

### 🔧 Internal

* **Async extension hooks:** All `CrewExtension` lifecycle hooks (`on_start`, `on_resume`, `on_step`, `on_pause`, `on_finish`) are now `async def`.

* **Extension error isolation:** Exceptions raised inside individual extension hooks are caught and logged as warnings instead of crashing the workflow. Execution continues with the remaining extensions.

* **`critical` extension attribute:** `CrewExtension` now exposes a `critical: bool = False` class attribute. When set to `True`, exceptions from that extension's hooks are re-raised instead of swallowed, halting the workflow. `WorkspaceSaver` and `GitCommitter` are marked critical by default.

## [0.11.3] - 2026-04-06

### 🚀 Added

* **Parallel tool calls:** Agents can now call multiple tools simultaneously in a single LLM response (e.g. `LoadSkill` + `RetrieveContext`). All intermediate tool calls are executed concurrently via `asyncio.gather`.

* **Batched skill loading:** `LoadSkill` now accepts a `skill_names` list instead of a single `skill_name`, allowing agents to load multiple skills in one tool call.

* **Source descriptions in `rag.yaml`:** Each source entry now supports an optional `description` field. Descriptions are embedded directly into the `RetrieveContext` tool schema so agents know what each source contains without an extra round-trip.

* **Default `config/rag.yaml`:** A bundled default RAG config is loaded when no `rag.yaml` is present in the project directory. Resolution order: CWD `rag.yaml` → bundled `config/rag.yaml` → `settings.py` values.

* **Tools configuration in agent's frontmatter:** Intermediate and final tools configuration for every agent is moved to the frontmatter of the agent's configuration file, for instance: `tools: [LoadSkill, RetrieveContext, AskClarification, SubmitSpecification]`.

* **Custom tool registry:** End users can now register custom intermediate tools (or override built-ins) via the `tool_registry`. Register a Pydantic schema and an async handler, then add the tool name to any agent's `tools:` frontmatter list.

* **`ReadFile` / `ListFiles` workspace tools:** Agents can now request workspace files on demand via `ReadFile` (read a single file by path) and `ListFiles` (list all available files). Files are resolved from in-memory state first, then from the live workspace folder on disk.

* **`GlobFiles` / `GrepFiles` workspace tools:** Agents can now search the workspace with `GlobFiles` (find files by path pattern, e.g. `*.py`, `src/**/*.ts`) and `GrepFiles` (search file contents by regex with optional glob filter).

### 🔧 Internal

* **Prompt partials:** Agent prompt templates now support `{ include 'partials/file.md' }` syntax to share common sections across agents. Partials are resolved from `config/agents/` with path traversal protection.

* **Config reorganization:** Moved `llms.yaml`, `rag.yaml` and `sandbox.yaml` into `config/tools/`. Added `settings.tools_config_dir` cached property to avoid repeating the path.

## [0.11.2] - 2026-04-04

### 🚀 Added

* **Bundled RAG Docker image (`Dockerfile.mydevteam-rag`):** A single container image that runs both Qdrant and the MCP server. Replaces the previous two-terminal setup - one `docker run` starts the entire RAG stack with no WSL required.

## [0.11.1] - 2026-04-03

### 🚀 Added

* **`mcp-ingest` chunking:** The ingest CLI now splits large documents into overlapping chunks before storing. Supports two strategies - `--split-by words` (word-based sliding window, default) and `--split-by sections`.

* **`--no-split` flag for `mcp-ingest`:** Stores the entire document as a single chunk, bypassing chunking. Mutually exclusive with `--split-by`.

* **`--rag-collection` CLI argument:** New `devteam` CLI flag to set the RAG collection name at runtime without modifying settings.

## [0.11.0] - 2026-04-03

### 🚀 Added

* **RAG support via MCP:** Agents can now retrieve context from an external knowledge base using a `RetrieveContext` tool. The tool calls a configurable MCP server (default: `qdrant/mcp-server-qdrant`) over Streamable HTTP, keeping the main app free of any vector store or embedding dependencies.

* **`mcp-ingest` CLI:** New command to ingest text files into the RAG knowledge base via the MCP server.

### 🔧 Internal

* **`RetrieveContext` tool (`agents/schemas.py`):** Pydantic tool schema with `query`, `source` filter, and `limit` fields. Handled as an intermediate tool - retrieved chunks are injected as a `ToolMessage` and the LLM re-evaluates with the new context, reusing the existing `LoadSkill` re-evaluation loop.

* **RAG opt-in via agent frontmatter:** Adding `rag: true` to any agent's `.md` config file enables the `RetrieveContext` tool for that agent automatically. Currently enabled for Product Manager and System Architect.

* **`tools/rag.py`:** Async MCP client that calls the configured RAG MCP server and formats retrieved chunks for injection into the LLM conversation.

* **RAG settings (`settings.py`):** Two new settings - `rag_mcp_url` (default: `http://localhost:8765`) and `rag_mcp_tool` (default: `qdrant-find`) - allow switching MCP backends via config with no code changes.

## [0.10.0] - 2026-04-01

### 🚀 Added

* **React GUI:** Replaced the Streamlit dashboard with a Vite + React JS web application served by a Flask backend. The new GUI features a sidebar navigation, live execution dashboard with Server-Sent Events streaming, and a minimalistic Tailwind CSS design.

* **Flask backend (`src/devteam/server/`):** REST API and SSE streaming server. Manages project execution in background threads, buffers all events for reconnecting clients, and serves the built React app as static files. Entry point `devteam-ui` now starts the Flask server instead of Streamlit.

* **Live execution dashboard:** Phase tracker (Planning → Development → Integration → Finished), interleaved Activity feed showing agent log entries (bold) and LLM thinking tokens (regular monospace) in chronological order, and a left panel with four tabs - Workspace files, Tasks, Specs, and Report - all updated in real time via SSE.

* **Inline HITL input:** Clarification questions from the Product Manager and spec/plan approval prompts are now handled directly in the dashboard without interrupting the workflow. The HITL extension is always active (not just when approval mode is enabled), so PM clarification questions are handled correctly in all configurations.

* **Markdown rendering:** Specs, final report, task descriptions, and agent activity log entries are rendered as formatted markdown (headings, bold/italic, bullet lists, code blocks).

### 🗑️ Removed

* Streamlit GUI (`src/devteam/gui/`) removed entirely.

## [0.9.2] - 2026-03-30

### 🚀 Added

* **Anthropic Provider Support:** Added `anthropic` as a supported LLM provider. Requires `ANTHROPIC_API_KEY` and `pip install langchain-anthropic`.

* **Compound Providers:** Introduced compound providers - pseudo-providers in `llms.yaml` whose individual model entries carry a `provider` field pointing to the real backend. The factory resolves the effective provider per-model at instantiation time, enabling a single `--provider` flag to transparently mix models from different backends.

* **Plan Approval Mode:** Added an interactive approval gate to the planning phase. When enabled, the workflow pauses twice - once after the Product Manager produces the Technical Specification, and once after the System Architect produces the task plan - and prompts the user to review and either approve or request rework.

### 🔧 Internal

* **Removed parallel task execution:** The LangGraph `Send` fan-out mechanism has been removed. Tasks now always execute sequentially, one at a time. The `dependencies` field is retained in task definitions and is still used to determine execution order.

## [0.9.1] - 2026-03-29

### 🔧 Internal

* **Tool Call Coercion Fallback:** Agents now gracefully handle models that output tool calls as plain-text JSON in the message content instead of using native tool calling (a known limitation of some smaller Ollama models).

* **Per-model `thinking` flag for Ollama:** Each Ollama model entry in `llms.yaml` now carries an explicit `thinking` boolean. Only models that declare `thinking: true` (currently `qwen3:8b`) have the Ollama reasoning/thinking stream enabled.

## [0.9.0] - 2026-03-29

### 🚀 Added

* **Parallel Task Execution (Fan-Out):** Development tasks are now dispatched in parallel based on their `dependencies` field. Tasks with no unmet dependencies are fanned out simultaneously as independent LangGraph branches using the `Send` API, and each branch runs its full developer → reviewer → QA cycle concurrently. Tasks with dependencies are dispatched automatically once all prerequisites complete, enabling dependency-level pipelining across the entire backlog.

* **Capability-Based LLM Routing:** Replaced the flat category-to-model mapping in `LLMFactory` with a capability scoring system. Each model in `llms.yaml` now declares a set of named capabilities with 0–1 proficiency scores. Agents request one or more capabilities - optionally with weights - and the factory selects the highest-scoring model by computing a weighted sum across all requested capabilities. This allows agents to express nuanced requirements (e.g., `code-generation: 0.7, reasoning: 0.3`) rather than a single fixed category, and makes it trivial to add new models without redefining routing rules.

* **New `planning` LLM capability:** Added a dedicated `planning` model category to `llms.yaml` for agents that perform task decomposition and architectural reasoning. This separates long-horizon planning workloads from deep code-focused `reasoning` tasks, allowing each provider to route them to the most suitable model. The System Architect's config was updated from `model: reasoning` to `model: planning`.

### ⚙️ Changed

* **Sequential execution is the default:** Tasks run one at a time by default. Use `--parallel` to opt in to fan-out execution.

* **System Architect prompt updated:** The architect is now explicitly instructed to maximize the number of independent (dependency-free) tasks and only add a dependency when it is a hard prerequisite, in order to expose as much parallelism as possible to the execution engine.

## [0.8.0] - 2026-03-28

### 🚀 Added

* **SKILLs System:** Introduced SKILLs - modular, reusable agent instructions and domain knowledge files. SKILLs can be attached to agents or workflows to extend capabilities, enforce coding standards, or inject project-specific expertise. See the documentation for usage patterns and authoring guidelines.

### 🔧 Internal

* **`ProjectState` migrated to Pydantic `BaseModel`:** `ProjectState` was rewritten from a `TypedDict` to a `BaseModel`. All fields now have explicit defaults, and LangGraph performs runtime validation on every state update.

* **Python Version:** Minimum required Python version is now 3.14. All code has been updated to use modern built-in generics (e.g., `list`, `dict`), the `@override` decorator, and other Python 3.14+ features. Legacy `typing` imports (`Dict`, `List`, `Optional`) have been removed.

## [0.7.1] - 2026-03-26

### 🚀 Added

* **Sandbox Control:** Added `--no-docker` flag to run QA engineer without Docker sandbox.

### ⚙️ Changed

* **Docker Sandbox:** Networking is now disabled for all Docker sandbox containers, improving test isolation and security.

### 🔧 Internal

* **New Docker Image:** Added a Dockerfile for Python 3.12 with pytest preinstalled at `src/devteam/config/docker/Dockerfile.python3.12-pytest`.

  **How to Build:**
  Run this command from your project root to build the image:

  ```sh
  docker build -t python:3.12-pytest -f src/devteam/config/docker/Dockerfile.python3.12-pytest .
  ```
  This image will run pytest by default in `/workspace`.

## [0.7.0] - 2026-03-25

### ⚙️ Changed

* **Hub-and-Spoke Architecture:** Migrated core system to a hub-and-spoke model. Centralized coordination logic in a single hub, with agents and components now acting as spokes.

* **Flat Graph Architecture:** Replaced nested subgraphs with a single flat `StateGraph` in `ProjectManager`. All nodes (`human`, `pm`, `architect`, `officer`, `developer`, `reviewer`, `qa`, `final_qa`, `reporter`) and edges are now defined in one graph. Removed `PlanningManager`, `StandardExecutionManager`, and `IntegrationManager` classes. Simplified `Execution` streaming (removed `subgraphs=True`) and `History` checkpoint traversal (removed subgraph namespace iteration).

## [0.6.1] - 2026-03-24

### 🐛 Fixed

* **WorkspaceSaver Path Traversal Hardening:** Prevented writes outside snapshot and live workspace roots by rejecting absolute paths and validating resolved paths remain within allowed directories before writing generated files.
* **GUI Thinking Mode Global State Leak:** Fixed streaming state persisting across GUI runs by explicitly setting `thinking` on each execution, preventing stale state from prior runs with different thinking settings.

## [0.6.0] - 2026-03-23

### 🚀 Added

* **Tool-Calling Agents:** `BaseAgent` now uses LLM-native tool calling (`bind_tools`) instead of structured JSON output. All agents submit their results via tools (e.g. `SubmitSpecification`, `SubmitCode`, `ApproveCode`, `ReportIssues`, `SubmitReport`, `SubmitWinner`).

### ⚙️ Changed

* **LLMFactory:** Added `json_mode` parameter (default `True`). When `False`, Ollama drops `format='json'` and enables `reasoning=True` for thinking model support. Groq skips `response_format` binding.
* **All Agents:** Migrated from structured JSON output parsing to tool calling. Prompts updated to reference tool names.
* **Reasoning Content Streaming:** `StreamHandler` now captures `reasoning_content` from Ollama's thinking models (e.g. qwen3) and streams it in real-time.

## [0.5.1] - 2026-03-22

### 🚀 Added

* **CrewFactory:** Added a dedicated `CrewFactory` to centralize and standardize crew instantiation.
* **LLM Thinking Output:** New `--thinking` CLI flag streams raw LLM token output (including `心智` reasoning) to stderr in real-time via a new `StreamHandler` callback. When enabled, all LLM instances are created with `streaming=True`.

## [0.5.0] - 2026-03-18

### 🚀 Added

* **GitCommitter Extension:** New `GitCommitter` extension that automatically initializes a local git repository inside the project's `workspace` subfolder and commits every developer update with a message of the form `Task {index} - revision {n}`.

### ⚙️ Changed

* **VirtualCrew Constructor:** `project_folder: Path` is now the first positional argument. `WorkspaceSaver` and `GitCommitter` are wired in as dedicated keyword parameters (`workspace_saver`, `git_committer`) with sensible defaults, so callers no longer need to pass them via the generic `extensions` list.

* **WorkspaceSaver Live Workspace:** In addition to writing versioned snapshots under `00_planning/`, `01_task/rev_N/`, etc., `WorkspaceSaver` now mirrors every developer-produced file to a flat `workspace` subfolder inside the project folder. This folder serves as the live working tree that `GitCommitter` tracks.

* **Phase-Driven Lifecycle State:** Introduced `current_phase` field (`planning`, `development`, `integration`, `complete`) in project state.

### 🐛 Fixed

* **Escaped Newline File Corruption:** Normalized malformed LLM file payloads containing literal `\\n` sequences before workspace merge, preventing invalid source files from being written and breaking test collection.

### 🔧 Internal

* **WorkspaceSaver Directory Routing by Phase:** Refactored target directory resolution to rely on `current_phase` instead of node-name heuristics, keeping planning/development/integration outputs aligned with the outer lifecycle graph.

* **Sanitization Helper Centralization:** Moved workspace content normalization into `utils.sanitizer` and reused it from schema validation for a single sanitization source of truth.

## [0.4.2] - 2026-03-17

### 🚀 Added

* **Live Execution Dashboard Enhancements:** The Streamlit UI now visualizes crew execution in real time with phase tracking, agent activity timeline, task progress, communication log, and generated workspace file previews.

* **Dedicated UI Launcher Command:** Added `devteam-ui` as a separate entry point to launch the Streamlit dashboard directly.

### ⚙️ Changed

* **Verbose Logging Cleanup:** Reduced runtime log noise by moving multiple internal messages from `INFO` to `DEBUG` (crew lifecycle checkpoints and telemetry accumulation/generation traces).

* **Resume Lifecycle Hook Flow:** Resume paths now consistently trigger extension resume hooks, enabling extensions to react to both plain resume and feedback-injection resume flows.

* **GUI Runtime Controls & Logging:** Added LLM timeout input to the UI (default `120s`) and applied the selected value to settings before run start. UI process logging now uses the same file logger pipeline as CLI.

### 🔧 Internal

* **Crew Config Loading Refactor:** Extracted crew YAML parsing into a dedicated helper (`load_crew_config`) to simplify the agent factory flow.

## [0.4.1] - 2026-03-16

### 🚀 Added

* **Bring Your Own Config (BYOC):** Added `--config` CLI flag allowing users to pass custom directories for agent prompts and LLM routing without forking the repository.

* **Customizable LLM Timeout:** Added `--timeout` CLI flag to globally control the maximum wait time for LLM responses, allowing users to easily adjust for slower local models (like Ollama) or incredibly fast cloud providers (like Groq).

* **Optimization & Token Leak Analyzer:** Upgraded the `TelemetryTracker` to not only count tokens and calculate costs but to actively analyze the AI crew's execution trajectory for inefficiencies.

* **Agent-Level Diagnostics:** The framework now uses LangChain `role:` tags to track exactly which agent is consuming tokens. At the end of a run, it generates a diagnostic report flagging "Context Bloat" (exponentially growing prompts), "Thrashing" (agents stuck in failure loops), and "High Waste Ratios" (sending massive context for tiny outputs).

### 🐛 Fixed

* **Optimization Diagnostics Bug:** Fixed an `unhashable type: 'list'` runtime error in the telemetry tracker by replacing a faulty set initialization with a proper set comprehension.

* **State Evaluation Crash:** Fixed a bug in the async stream loop of the `execute` method where it attempted to read `final_state` before the loop completed. Now safely evaluates `full_state` during active iteration.

### 🔧 Internal

* **Configuration-Driven Agent Factory:** Migrated the crew instantiation logic out of the Python codebase and into a centralized `config/crew.yaml` file. The `build_crew` factory now utilizes Python module reflection (`getattr`) to dynamically instantiate agent classes based on the YAML blueprint.

* **Explicit Agent Tagging:** Refactored `BaseAgent.from_config` initialization to explicitly accept a `node_name` parameter. This string is injected as a LangChain tag (`node:{node_name}`) during LLM creation, ensuring telemetry and cost tracking remain perfectly stable even if underlying class names are refactored.

## [0.4.0] - 2026-03-15

### 🚀 Added

* **Streamlit Web Dashboard (`app.py`):** Introduced a fully interactive graphical user interface. Users can now start new projects via file upload, view the granular execution timeline in a sortable data table, and use a visual form to inject time-travel feedback.

* **Time Travel & State Injection (Human-in-the-Loop):** Added `--feedback` and `--as-node` arguments to the CLI. The framework can now intercept graph execution, inject human feedback directly into the SQLite state, and force LangGraph to route backward (e.g. impersonating the `reviewer` to send tasks back to the `developer`).

* **True Time Travel (`--checkpoint`):** Upgraded the state injection feature to support true timeline rewinding. Users can now pass a specific checkpoint ID to fork the graph from a past state, preventing race conditions where the graph had already moved on to the next task before feedback was injected.

* **Granular Timeline History (`--history`):** Added a CLI flag to print a formatted, chronological timeline of the crew's execution.

## [0.3.0] - 2026-03-14

### 🚀 Added

* **Universal Runtime Support:** The `DockerSandbox` is no longer hardcoded to Python. It now supports a registry of languages (Python, Node.js, etc.) via a centralized `config/sandbox.yaml` file.

* **Architect-Driven Tech Stacks:** The `SystemArchitect` agent now explicitly defines the project's `runtime` in its output schema, which dictates the Docker container and test commands used by the QA Engineer.

* **Builder Pattern for Agents:** Introduced `.with_sandbox()` to the `QAEngineer` class, allowing cleaner, fluent dependency injection in the `build_crew` factory without polluting the `BaseAgent` class.

### ⚙️ Changed

* **Detached Docker Execution:** Upgraded `DockerSandbox.run_tests()` to run containers in `detach=True` mode with a `.wait()` block. This guarantees 100% capture of `stdout/stderr` logs, even if the container crashes instantly on import.

* **Language-Agnostic QA Prompts:** Completely rewrote the `qa-engineer-sandbox.md` prompt. Removed Python-specific jargon (`pytest`, `Traceback`) in favor of universal testing concepts (Compilation Errors, Stack Traces, Test Frameworks) to support multi-language CI/CD.

* **Strict Prompt Hierarchies:** Restructured the QA Engineer's diagnostic instructions into a strict, numbered hierarchy (Rules 1-4) to prevent smaller local models (like 7B) from eagerly pattern-matching the wrong errors.

* **Developer Test Enforcement:** Updated the `senior-developer.md` prompt to strictly enforce TDD (requiring at least two files per task) and wrapping CLI logic in `__main__` guards to prevent execution during test collection.

### 🐛 Fixed

* **Async Checkpointer Crashes:** Fixed `asyncio.exceptions.InvalidStateError` and `AttributeError` by replacing synchronous LangGraph calls (`get_state`, `update_state`) with their proper async counterparts (`aget_state`, `aupdate_state`) in the `VirtualCrew.execute` loop.

* **Python Pathing Errors:** Injected `PYTHONPATH=/workspace` into the Docker environment variables to resolve `ModuleNotFoundError` issues when `pytest` attempts to import files from the `src/` directory.

* **Network Isolation Blocking Tests:** Disabled `network_disabled=True` in the Docker Sandbox to allow the container to correctly fetch testing frameworks (like `pytest`) during the test run.

* **Agent Hallucinations on "0 Items Collected":** Fixed an edge case where test runners throwing collection errors (like broken imports) were misidentified by the LLM as "missing test files".

## [0.2.0] - 2026-03-13

### 🚀 Added

* **Intelligent Model Routing (`LLMFactory`):** Added semantic routing to dynamically assign the most cost-effective and capable models based on task category (`reasoning`, `code-generator`, `code-analyzer`, `fast-utility`) and chosen provider (`groq`, `ollama`, `openai`).

* **Command Line Interface (CLI):** Built the `devteam` CLI tool to kick off projects directly from a `project.txt` file, complete with `--provider` and `--rpm` (Rate Limiter) arguments.

* **Strict Test-Driven Development (TDD):** Enforced an architecture where the System Architect embeds testing criteria into every JSON task, and the Developer writes unit tests alongside the implementation code.

* **Rate Limiting & Telemetry:** Added a `RateLimiter` to safely manage API quotas and a `TelemetryTracker` to calculate token usage and latency.

### ⚙️ Changed

* **Centralized Prompt Configuration:** Abstracted all agent personas, system instructions, and constraints out of Python strings and into clean Markdown files with YAML frontmatter (`config/agents/**`).

* **Structured Outputs:** Overhauled graph state management to strictly use Pydantic and LangChain's structured output parsers, entirely eliminating "Markdown spillage" and broken JSON payloads.

* **Async Execution:** Migrated the `VirtualCrew.execute` workflow and SQLite checkpointer to fully asynchronous operations for better performance.

## [0.1.0] - 2026-03-09

### 🚀 Added

* **Multi-Agent Architecture:** Introduced the core autonomous AI agency powered by LangGraph. Specialized agents include `ProductManager`, `SystemArchitect`, `SeniorDeveloper`, `CodeReviewer`, `QAEngineer`, `FinalQAEngineer`, and `Reporter`.

* **Extensions System:** Implemented pluggable lifecycle hooks, including `WorkspaceSaver` (for writing generated code to disk) and `HumanInTheLoop` (for pausing the graph and requiring manual user approval).
