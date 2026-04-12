# RAG Knowledge Base

RAG (Retrieval-Augmented Generation) lets agents query an external knowledge base before producing output. Retrieved content is injected into the conversation and the LLM re-evaluates with that context - allowing agents to reason over your team's actual documentation, tickets and standards rather than relying solely on training data.

---

## How It Works

RAG is built on two concepts: a **knowledge base** and an **MCP access layer**.

### Knowledge Base

The knowledge base is where your documents live. This can be:

- **Qdrant** - a dedicated vector database, recommended as the universal knowledge base for this app. Accepts any document you ingest via `mcp-ingest`.
- **Confluence** - your existing Confluence spaces, queried directly via MCP without ingestion
- **Jira** - your existing Jira projects, queried directly via MCP without ingestion
- **SharePoint / other** - any system for which an MCP server exists

You can use one or several simultaneously. Each source is accessed through its own MCP server.

### MCP Access Layer

The app never connects to a knowledge base directly. Instead, each knowledge base exposes a search interface via an MCP server. The app calls the MCP server, which handles querying, embedding and result formatting.

```
MyDevTeam app
    --> MCP server (Qdrant)      --> Qdrant vector DB
    --> MCP server (Atlassian)   --> Confluence / Jira
    --> any other MCP server     --> any other source
```

The app requires no vector store client, no embedding library and no knowledge base SDK.

---

## Recommended Setup: Qdrant

Qdrant is recommended as the primary knowledge base when you want to ingest your own documents (coding standards, architecture decisions, specs, PDFs, Markdown files). It is free, self-hosted, and works offline.

The MCP server for Qdrant is [`mcp-server-qdrant`](https://github.com/qdrant/mcp-server-qdrant), which handles embedding and semantic search internally using `fastembed`.

---

## Overview

When using Qdrant, two services must be running before starting the app:

| Service | What it does | Port |
|---|---|---|
| **Qdrant** | Stores and searches document vectors | 6333 |
| **MCP server** | Exposes Qdrant search as an MCP tool | 8000 |

```
MyDevTeam app  -->  MCP server (:8000)  -->  Qdrant (:6333)
```

---

## Installation

Install the RAG optional dependencies in your Python environment:

```sh
pip install "my-dev-team[rag]"
```

This installs `mcp` (required for agent context retrieval) and `vectorize-me` (provides the `mcp-ingest` CLI for ingesting documents).

---

## Starting the RAG Stack

### Option A - Bundled Docker image (recommended)

A bundled Docker image runs both Qdrant and the MCP server in a single container. **No WSL required.**

**Build the image (one time, from the repo root):**

```sh
docker build -t mydevteam-rag -f src/devteam/config/docker/Dockerfile.mydevteam-rag .
```

**Run:**

```sh
docker run -d \
  -p 6333:6333 -p 8000:8000 \
  -e COLLECTION_NAME=myproject \
  -v ~/qdrant/storage:/qdrant/storage \
  --name mydevteam-rag \
  mydevteam-rag
```

Replace `myproject` with your collection name. The MCP server listens on `http://127.0.0.1:8000/mcp`.

> The collection name is the bucket all documents are stored in. Use the same name when ingesting and when running the app.

---

### Option B - Separate services (manual setup)

Use this if you prefer to run Qdrant and the MCP server independently, or if you already have Qdrant running.

**Step 1 - Start Qdrant.**

Docker:

```sh
docker run -p 6333:6333 -v ~/qdrant/storage:/qdrant/storage qdrant/qdrant
```

Or native binary on WSL (no Docker):

```sh
# Download binary (one time)
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-musl.tar.gz \
  | tar -xz -C ~/qdrant

# Create storage config (one time)
mkdir -p ~/qdrant/storage
cat > ~/qdrant/config.yaml << 'EOF'
storage:
  storage_path: ./storage
EOF

# Run
cd ~/qdrant && ./qdrant
```

> **WSL note:** Qdrant on `localhost:6333` is forwarded to Windows automatically by WSL2. If unreachable, run `wsl hostname -I` and use that IP instead.

**Step 2 - Start the MCP server.**

Install `uv` on WSL (one time):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
```

Run in a **WSL terminal** (separate from Qdrant). Replace `myproject` with your collection name:

```sh
QDRANT_URL=http://localhost:6333 COLLECTION_NAME=myproject \
  uvx mcp-server-qdrant --transport streamable-http
```

The MCP server listens on `http://127.0.0.1:8000/mcp`.

> The collection name is the bucket all documents are stored in. Use the same name when ingesting and when running the app.

---

## Ingesting Documents

Use the bundled `mcp-ingest` CLI (run on **Windows** in your project directory). Replace `path/to/document.txt` in the examples below with the actual path to your file.

**Plain text - word-based chunking (default):**

```sh
mcp-ingest path/to/document.txt --title "My Document" --source files
```

**Markdown - split on `##` headings (recommended for structured docs):**

```sh
mcp-ingest path/to/document.md --split-by sections --title "Architecture Decisions"
```

**Large plain text - tune chunk size:**

```sh
mcp-ingest path/to/large.txt --chunk-size 256 --overlap 32
```

**Single chunk - no splitting:**

```sh
mcp-ingest path/to/small.txt --no-split
```

A sample standards file is provided in `examples/rag/python_coding_standards.md`:

```sh
mcp-ingest examples/rag/python_coding_standards.md --split-by sections --title "Python Coding Standards"
```

**All options:**

| Flag | Default | Description |
|---|---|---|
| `--split-by words\|sections` | `words` | Chunking strategy |
| `--chunk-size N` | `512` | Chunk size in words (words strategy only) |
| `--overlap N` | `64` | Overlap in words between chunks (words strategy only) |
| `--no-split` | - | Store entire document as one chunk |
| `--source` | `files` | Source tag for filtering (`jira`, `confluence`, `files`) |
| `--title` | file name | Document title stored in metadata |
| `--collection` | from settings | Qdrant collection name |
| `--mcp-url` | from settings | MCP server URL |

---

## Verifying Documents Are Stored

```sh
curl -s http://localhost:6333/collections/myproject/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "with_payload": true}' | python3 -m json.tool
```

---

## Running the App with RAG

```sh
devteam project.txt --rag-collection myproject
```

To disable RAG at runtime even for agents that have `rag: true`:

```sh
devteam project.txt --no-rag
```

---

## Multi-Source Configuration

By default the app queries a single Qdrant MCP server. To add additional sources (Jira, Confluence or any other MCP-compatible search tool), create a `rag.yaml` file in your project root.

A template is provided:

```sh
cp examples/rag/rag.yaml rag.yaml
```

Edit `rag.yaml` to point each source to its MCP server. The optional `description` field is shown to agents so they know what each source contains:

```yaml
sources:
  default:
    mcp_url: http://localhost:8000/mcp
    mcp_tool: qdrant-find
    description: "Internal docs, coding standards and architecture decisions"
  jira:
    mcp_url: http://localhost:9000/mcp
    mcp_tool: jira_search_issues
    description: "Bug reports, feature requests and sprint tickets"
  confluence:
    mcp_url: http://localhost:9000/mcp
    mcp_tool: confluence_search
    description: "Team wiki, runbooks and meeting notes"
```

**Proprietary ticketing system example:** If your team uses an internal ticketing system (e.g. ServiceNow, YouTrack or a custom tool), expose it as an MCP server and add it as a named source:

```yaml
sources:
  default:
    mcp_url: http://localhost:8000/mcp
    mcp_tool: qdrant-find
  tickets:
    mcp_url: http://your-ticketing-mcp-server/mcp
    mcp_tool: search_tickets
```

Agents can then call `RetrieveContext` with `source=tickets` to search your ticketing system directly. Any MCP-compatible server works - the app treats all sources uniformly through the same protocol.

When an agent calls `RetrieveContext` with a named source, it queries that source's MCP server directly. Sources not listed in `rag.yaml` are passed as payload filters to the default Qdrant server instead.

`rag.yaml` is user-specific and excluded from version control via `.gitignore`. If absent, the app loads the bundled default config (single Qdrant source on `localhost:8000`). Settings in `settings.py` are used only when no `rag.yaml` is found at all.

---

## Configuration

Override default MCP server settings in `settings.py`:

```python
settings.rag_mcp_url = 'http://localhost:8000/mcp'   # default when no rag.yaml present
settings.rag_mcp_tool = 'qdrant-find'                # default when no rag.yaml present
```

---

## Enabling RAG per Agent

Add `rag: true` to the agent's `.md` frontmatter:

```yaml
---
role: Product Manager
capabilities: [reasoning]
temperature: 0.4
rag: true
---
```

Remove the flag to disable RAG for that agent. No Python code changes needed.
