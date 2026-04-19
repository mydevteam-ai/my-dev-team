# CLI Reference

My Dev Team ships three commands: `devteam` (the main runner), `devteam-ui` (the web dashboard) and `mcp-ingest` (RAG ingestion).

---

## `devteam`

Runs the autonomous AI development workflow from the terminal.

```
devteam [project_file] [options]
```

Either `project_file` or `--resume` (or `--history`) is required.

### Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `project_file` | positional (optional) | - | Path to the requirements text file. Omit only when using `--resume`. |
| `--provider` | choice | `ollama` | LLM backend. Options: `anthropic`, `azure-anthropic`, `azure-openai`, `free`, `groq`, `ollama`, `openai`. See [LLM providers](llm.md) for model lists and required env vars. |
| `--azure` | flag | off | Use the Azure-hosted variant of the selected provider. `--provider openai --azure` is equivalent to `--provider azure-openai`. Errors if the provider already has an `azure-` prefix. |
| `--rpm` | int | `0` | API requests per minute. `0` disables rate limiting. |
| `--timeout` | int | `120` | Maximum seconds to wait for an LLM response. Increase for slow local models. |
| `--resume` | str | - | Resume an existing thread by ID (e.g. `web_scraper_cli_20260312_083500`). |
| `--feedback` | str | - | Human feedback to inject into the state when resuming. |
| `--as-node` | choice | `reviewer` | Which agent delivers the injected feedback. Options: `pm`, `architect`, `reviewer`, `qa`. Controls graph routing after injection. |
| `--history` | str | - | Print the checkpoint timeline for the given thread ID and exit (e.g. `--history web_scraper_cli_20260312_083500`). |
| `--checkpoint` | str | - | Checkpoint ID to rewind to before resuming or injecting feedback. |
| `--ask-approval` | flag | off | Pause after the PM produces the Technical Specification and again after the Architect produces the task plan, waiting for interactive approval before proceeding. |
| `--thinking` | flag | off | Stream raw LLM thinking tokens to stderr in real time. |
| `--no-docker` | flag | off | Run the QA Engineer without a Docker sandbox (LLM-based simulation only). |
| `--rag-collection` | str | - | Vector store collection name for RAG queries. Only needed when the MCP server has no locked-in `COLLECTION_NAME`. |
| `--no-rag` | flag | off | Disable RAG context retrieval entirely for all agents. |
| `--seed` | str | - | Path to a local directory or `.zip` archive to copy into the workspace before agents run. Cannot be combined with `--resume`. |
| `--config` | str | - | Path to a custom configuration directory, overriding the bundled `config/`. |
| `--settings` | str | - | Path to a custom `config.yaml`, overriding the default lookup (`./config.yaml` then `~/.devteam/config.yaml`). |
| `--workflow` | str | `development` | Workflow variant to run. Options: `development` (default), `migration`. Append `-fanout` to any workflow (e.g. `development-fanout`, `migration-fanout`) to enable fan-out mode. Use `--fanout` as a shorthand when the workflow flag is already set or defaulted. |
| `--fanout` | flag | off | Run two developers independently on each task and let a Code Judge pick the best implementation before code review. The winning developer handles all subsequent revisions. Combinable with any `--workflow`. |
| `--verbose` | flag | off | Enable debug-level logging to the console. |

### Persistent defaults

Any flag can be set permanently in a `config.yaml` file so you don't have to repeat it on every run. See [Configuration file](config.md) for the full reference.

### Project file format

The crew extracts the project name and thread ID from a `Subject:` header line:

```
Subject: NEW PROJECT: Web Scraper CLI

I need a Python CLI that scrapes articles from a URL.
It should extract the title, author and body text, then save output as JSON.

Requirements:
- Use BeautifulSoup4 for parsing.
- Include --url and --output arguments.
- Write unit tests for the parsing logic.
```

If no `Subject:` line is present, the file name is used as the project name.

### Examples

**Start a new project with the default Ollama provider:**
```sh
devteam project.txt
```

**Run with Groq, capped at 30 requests per minute:**
```sh
devteam project.txt --provider groq --rpm 30
```

**Run with OpenAI and stream LLM thinking to stderr:**
```sh
devteam project.txt --provider openai --thinking
```

**Run without Docker (LLM-based QA only):**
```sh
devteam project.txt --no-docker
```

**Pause for human approval of the spec and task plan before development:**
```sh
devteam project.txt --ask-approval
```

**Increase timeout for slow local models:**
```sh
devteam project.txt --provider ollama --timeout 300
```

**Use a custom configuration directory:**
```sh
devteam project.txt --config ./my-config/
```

**Resume an interrupted run:**
```sh
devteam --resume web_scraper_cli_20260312_083500
```

**Resume and inject reviewer feedback:**
```sh
devteam --resume web_scraper_cli_20260312_083500 --feedback "Add input validation and error handling"
```

**Inject feedback routed to the PM (triggers re-planning):**
```sh
devteam --resume web_scraper_cli_20260312_083500 \
  --feedback "Scope reduced: drop the JSON export feature" \
  --as-node pm
```

**Rewind to a specific checkpoint before resuming:**
```sh
devteam --resume web_scraper_cli_20260312_083500 \
  --checkpoint 1a2b3c4d-... \
  --feedback "Try a different approach for the parser"
```

**Print the checkpoint timeline for a thread:**
```sh
devteam --history web_scraper_cli_20260312_083500
```

**Query RAG with a specific collection name:**
```sh
devteam project.txt --rag-collection myproject
```

**Disable RAG entirely:**
```sh
devteam project.txt --no-rag
```

**Seed the workspace from an existing local project:**
```sh
devteam project.txt --seed /path/to/existing/code
```

**Seed from a ZIP archive:**
```sh
devteam project.txt --seed export.zip
```

**Run two developers on each task and let a judge pick the best:**
```sh
devteam project.txt --fanout
devteam project.txt --workflow fanout
devteam project.txt --fanout --provider groq --rpm 30
```

**Use an Azure-hosted provider:**
```sh
devteam project.txt --provider openai --azure
devteam project.txt --provider anthropic --azure
```

---

## `devteam-ui`

Starts the web dashboard (Flask + React). Requires `pip install "my-dev-team[ui]"` and a one-time frontend build.

```
devteam-ui
```

No arguments. The server reads host and port from environment variables (`HOST`, `PORT`). Loads `.env` automatically.

```sh
pip install "my-dev-team[ui]"
devteam-ui
```

> **Local development:** If you installed from source with `pip install -e .`, the pre-built `dist/` files are not present. Build the frontend once before launching:
> ```sh
> cd gui && npm install && npm run build
> ```

---

## `mcp-ingest`

Ingests a text or Markdown file into the RAG vector store via the MCP server.

```
mcp-ingest <file> [options]
```

### Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `file` | positional | - | Path to the file to ingest. |
| `--source` | str | `files` | Source tag attached to each chunk as metadata, used for filtering in `RetrieveContext`. |
| `--title` | str | file name | Document title stored in chunk metadata. |
| `--collection` | str | settings default | Vector store collection name to write into. |
| `--mcp-url` | str | settings default | MCP server URL (e.g. `http://localhost:8000/mcp`). |
| `--split-by` | choice | `words` | Chunking strategy: `words` (sliding window) or `sections` (splits on `##` Markdown headings). Mutually exclusive with `--no-split`. |
| `--chunk-size` | int | `512` | Chunk size in words. Only applies when `--split-by=words`. |
| `--overlap` | int | `64` | Word overlap between consecutive chunks. Only applies when `--split-by=words`. |
| `--no-split` | flag | off | Store the entire file as a single chunk. Mutually exclusive with `--split-by`. |

### Examples

**Ingest a plain text file with default word-based chunking:**
```sh
mcp-ingest docs/architecture.md
```

**Ingest a Markdown file split by headings:**
```sh
mcp-ingest docs/api-guide.md --split-by sections
```

**Ingest as a single chunk (short documents, no splitting needed):**
```sh
mcp-ingest docs/glossary.md --no-split
```

**Tag the document with a custom source and title:**
```sh
mcp-ingest tickets/PROJ-42.txt --source jira --title "PROJ-42: Auth redesign"
```

**Ingest into a specific collection with a custom chunk size:**
```sh
mcp-ingest docs/spec.md --collection myproject --chunk-size 256 --overlap 32
```

**Point to a non-default MCP server:**
```sh
mcp-ingest docs/spec.md --mcp-url http://192.168.1.10:8000/mcp
```
