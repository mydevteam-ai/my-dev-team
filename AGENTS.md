# AGENTS.md - My Dev Team

## Project Overview

**My Dev Team** is an autonomous, LangGraph-powered AI development agency. It takes raw project requirements and processes them through a multi-agent workflow (Product Manager → System Architect → Developer → Code Reviewer → QA → Reporter) to incrementally build, test, and deliver production-ready code.

- **Language:** Python 3.10+
- **Core frameworks:** LangGraph, LangChain, LiteLLM, Pydantic v2
- **Package manager:** pip / setuptools
- **Entry points:** `devteam` (CLI), `devteam-ui` (Streamlit dashboard)
- **License:** Apache-2.0

---

## Repository Structure

```
mydevteam/
├── pyproject.toml              # Build config, dependencies, entry points, pylint settings
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Pinned runtime dependencies
├── requirements-dev.txt        # Dev/test dependencies (pylint, pytest, build, twine, streamlit)
├── docs/                       # Documentation (MkDocs-style)
├── examples/                   # Sample project requirement files
├── src/devteam/                # Main package
│   ├── __init__.py
│   ├── settings.py             # Module-level globals with getter/setter functions
│   ├── agents/                 # AI agent implementations
│   ├── cli/                    # CLI entry point with arguments parsing
│   ├── config/                 # Bundled configuration (shipped with package)
│   ├── crew/                   # Crew orchestration
│   ├── extensions/             # Lifecycle hook extensions
│   ├── gui/                    # Streamlit web dashboard
│   ├── managers/               # LangGraph state-graph routing managers
│   ├── state/                  # LangGraph state definitions
│   ├── tools/                  # Agent tools (e.g. Docker sandbox)
│   └── utils/                  # Shared utilities
└── tests/                      # Test suite
```

---

## Coding Style

### Python Version & Syntax

- **Target Python 3.10+.** Use modern syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`, `match/case` for routing logic.
- Max line length is **190** characters (configured in `pyproject.toml` under `[tool.pylint.format]`).
- Docstrings are minimal and optional ? `missing-docstring` is disabled in pylint. When present, use one-line triple-double-quote style: `"""Brief description."""`

### Text Style

- Use a hyphen-minus (`-`) as a dash in all written text. Never use an em dash (`—`) or en dash (`–`). This applies everywhere: comments, docstrings, markdown files, log messages, CLI help text, and any other written output. Automatically replace any `—` or `–` you produce with `-`.
- Do not use the Oxford comma. In a list of three or more items, omit the comma before the final "and" or "or". Write "apples, oranges and bananas" not "apples, oranges, and bananas".

### Quoting Convention

**Double quotes (`"..."`) are reserved exclusively for human-readable, meaningful strings:**
- Log messages: `self.logger.info("Starting execution for task %s", task_id)`
- User-facing text, prompts, error messages: `"Failed to load config file"`
- Pydantic `Field(description="...")` values
- Docstrings (triple double quotes)

**Single quotes (`'...'`) everywhere else:**
- Dictionary keys: `state['workspace_files']`
- File and path names: `'config/tools/llms.yaml'`
- Module/class/attribute names as strings: `'planning'`, `'development'`
- Import-related strings: `'devteam.agents'`
- YAML keys, config identifiers: `'reasoning'`, `'code-generator'`
- Variable string values that are not user-facing: `encoding='utf-8'`

### Type Hints

- Use type annotations on all public function signatures (parameters and return types).
- Use modern union syntax: `str | list[str]`, `int | float`.
- For optional parameters with a `None` default, use `str = None` not `str | None = None` - the `None` default already implies optionality.
- **Exception:** Pydantic tool schemas exposed to LLMs (subclasses of `BaseModel` used as tools) must use `str | None = None` for nullable fields. Without `| None`, Pydantic generates `"type": "string"` in the JSON schema which rejects `null` values the LLM passes explicitly, causing tool call validation errors.
- Use `TypeVar` with `Generic[T]` for generic classes (see `BaseAgent[T]`).
- Use `TypedDict` with `Annotated` for LangGraph state definitions.
- `Any` is acceptable for opaque third-party objects (e.g. LangGraph app instances).

### Imports

1. **Standard library** imports first.
2. **Third-party** imports second.
3. **Local/project** imports last.
4. Use **relative imports** within the same package (`from .schemas import ...`, `from .base_agent import BaseAgent`).
5. No extra blank lines between import groups ? keep imports compact.
6. Within the **local/project** group, order imports from least to most specific:
   - `from devteam import ...` (top-level package symbols, e.g. `settings`)
   - `from devteam.utils import ...` (utility sub-package)
   - `from devteam.utils.something import ...` (specific utility module)

### Naming

- **Classes:** `PascalCase` ? `BaseAgent`, `VirtualCrew`, `ProjectManager`
- **Functions/methods:** `snake_case` ? `_build_inputs`, `route_planning`
- **Private members:** single underscore prefix ? `_invoke_llm`, `_parse_outputs`
- **Constants:** `UPPER_SNAKE_CASE` ? `STATE_DB_FILE`, `BASIC_CREW`
- **Module-level private globals:** `_UPPER_SNAKE_CASE` ? `_CONFIG_DIR`, `_LLM_TIMEOUT`

### Logging

- Use stdlib `logging` module, never bare `print()` for operational output (`rich.print` is acceptable for user-facing CLI output).
- Use `%s`-style placeholders in log messages (not f-strings): `self.logger.debug("Loaded %s agents", count)`
- Agents inherit `WithLogging` mixin which provides `self.logger` as a `cached_property`.

### Patterns & Architecture

- **Mixin-based composition** over deep inheritance ? combine `WithLogging`, `CommunicationLog`, `EventEmitter`, etc.
- **`functools.cached_property`** for lazy initialization of expensive attributes (`self.llm`, `self.chain`, `self.logger`).
- **Async execution** ? core loop uses `async/await` with `asyncio.run()` at the CLI boundary. Use `asyncio.wait_for()` for timeouts.
- **Pydantic `BaseModel`** for all structured LLM outputs and tool-calling schemas. Use `field_validator` with `mode='before'` for input normalization.
- **Agent config** is defined in Markdown files with YAML frontmatter (`---` delimiters) containing role, model category, temperature, and I/O field names.

### Error Handling

- `BaseAgent.process()` catches broad `Exception` and stores `traceback.format_exc()` in state ? agents must not crash the graph.
- CLI validates inputs early and exits with `sys.exit(1)` on configuration errors.
- Chain `from None` on re-raised exceptions to suppress noisy tracebacks: `raise TimeoutError(...) from None`

### Testing

- **Framework:** pytest (config in `pytest.ini`).
- Group related tests in classes: `class TestCodeReviewer:`, `class TestSeniorDeveloper:`.
- Use `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`) and pytest fixtures (`monkeypatch`, `tmp_path`).
- Tests are synchronous ? test `_build_inputs`, `_update_state`, and schema validation directly rather than full async `process()`.
- Use `pytest.mark.parametrize` for data-driven test cases.
- Assertions are plain `assert` statements.

---

## Changelog

- Always add new changelog entries under the version number from `pyproject.toml` (e.g. if `pyproject.toml` has `version = "0.9.2"`, add entries under `## [0.9.2]`).
- If that section does not exist yet, create it at the top of the version list with `- Unreleased` as the date.

---

## Build & Run

```sh
# Install in development mode
pip install -e .

# Run CLI
devteam project.txt

# Run Streamlit dashboard
devteam-ui

# Run tests
pytest

# Lint
pylint src/devteam
```
