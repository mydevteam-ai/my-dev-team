# Tools

Tools are actions that agents can call during their LLM conversation. When an agent calls a tool, the result is injected back into the conversation as a `ToolMessage` and the LLM continues reasoning with that new context.

There are two kinds of tools:

- **Intermediate tools** - executed mid-conversation and return results to the LLM (e.g. `ReadFile`, `LoadSkill`). These are handled by the tool registry.
- **Output tools** - signal the agent's final answer (e.g. `SubmitCode`, `ApproveCode`). These are parsed as structured output and written to state.

---

## Configuration

Each agent declares its tools in the YAML frontmatter of its config file (`config/agents/*.md`):

```yaml
---
role: Senior Developer
tools: [LoadSkill, ReadFile, ListFiles, GlobFiles, GrepFiles, SubmitCode]
---
```

The `tools` list controls which tool schemas are bound to the LLM. An agent can only call tools that appear in its list.

---

## Built-in Tools

| Tool | Type | Description |
|------|------|-------------|
| `LoadSkill` | Intermediate | Load specialized framework rules and best practices before writing code. |
| `RetrieveContext` | Intermediate | Retrieve relevant context from the RAG knowledge base. Only available when RAG is enabled. |
| `ReadFile` | Intermediate | Read a specific file from the workspace by relative path. Checks in-memory state first, then the live workspace folder on disk. |
| `ListFiles` | Intermediate | List all files available in the workspace (both in-memory and on disk). |
| `GlobFiles` | Intermediate | Find workspace files matching a glob pattern (e.g. `*.py`, `src/**/*.ts`). |
| `GrepFiles` | Intermediate | Search workspace file contents by regex pattern. Supports an optional `glob` filter to narrow which files to search. |
| `AskClarification` | Output | Ask the stakeholder a clarifying question. |
| `SubmitSpecification` | Output | Submit technical specifications. |
| `SubmitArchitecture` | Output | Submit the development task backlog. |
| `SubmitCode` | Output | Submit created or modified code files. |
| `ApproveCode` | Output | Approve code that meets acceptance criteria. |
| `ReportIssues` | Output | Report bugs or failing tests. |
| `SubmitWinner` | Output | Submit the index of the best code draft. |
| `SubmitReport` | Output | Submit the final stakeholder report. |

---

## Custom Tools

You can register custom intermediate tools (or override built-ins) via the `tool_registry`. A custom tool has three parts:

1. A **Pydantic schema** - the tool definition the LLM sees (name, description, parameters)
2. An **async handler** - the function that runs when the LLM calls the tool
3. A **registration call** - connects the name to the schema and handler

### Handler Signature

```python
async def my_handler(tool_args: dict, state: ProjectState, logger: logging.Logger) -> str:
    ...
```

- `tool_args` - the arguments the LLM passed to the tool
- `state` - the current `ProjectState` (workspace files, specs, etc.)
- `logger` - the calling agent's logger

### Example: SearchCode Tool

```python
from pydantic import BaseModel, Field
from devteam.tools import tool_registry

# 1. Define the schema (what the LLM sees)
class SearchCode(BaseModel):
    """Search the workspace for a pattern and return matching lines."""
    pattern: str = Field(description="Regex pattern to search for.")

# 2. Define the handler (what runs when the LLM calls the tool)
async def handle_search_code(tool_args, state, logger):
    import re
    pattern = tool_args['pattern']
    logger.info("Searching workspace for: %s", pattern)
    matches = []
    for path, content in state.workspace_files.items():
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(pattern, line):
                matches.append(f"{path}:{i}: {line.strip()}")
    return '\n'.join(matches) if matches else f"No matches for '{pattern}'."

# 3. Register
tool_registry.register('SearchCode', SearchCode, handle_search_code)
```

Then add `SearchCode` to any agent's frontmatter:

```yaml
---
role: Senior Developer
tools: [LoadSkill, ReadFile, ListFiles, SearchCode, SubmitCode]
---
```

### Overriding Built-in Tools

To replace a built-in tool, register with the same name. Your handler replaces the default:

```python
from devteam.tools import tool_registry
from devteam.agents.schemas import ReadFile

async def custom_read_file(tool_args, state, logger):
    path = tool_args['path']
    logger.info("Custom ReadFile: %s", path)
    # your custom logic here
    return f"--- FILE: {path} ---\n..."

tool_registry.register('ReadFile', ReadFile, custom_read_file)
```

### When to Register

Register custom tools before the crew starts. If you use the CLI, the simplest approach is a small wrapper script:

```python
from devteam.cli.main import main
from devteam.tools import tool_registry

# register your tools here
tool_registry.register('MyTool', MyToolSchema, my_handler)

main()
```
