# RAG Knowledge Base

Agents configured with `rag: true` in their frontmatter can call a `RetrieveContext` tool to query an external knowledge base before producing output. Retrieved chunks are injected into the conversation and the LLM re-evaluates with the new context.

The main app communicates with the knowledge base exclusively over MCP - no vector store client or embedding library is required.

---

## Overview

RAG requires two services running before you start the app:

| Service | What it does | Where it runs |
|---|---|---|
| **Qdrant** | Stores and searches document vectors | Docker or WSL binary |
| **MCP server** | Exposes Qdrant search as an MCP tool | WSL or any Linux host |

Both must be running. The app talks only to the MCP server; the MCP server talks to Qdrant.

```
MyDevTeam app  -->  MCP server (:8000)  -->  Qdrant (:6333)
```

---

## Installation

Install the `mcp` package in your Python environment (Windows):

```sh
pip install mcp
```

Install `uv` on WSL (required to run the MCP server):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
```

---

## Starting Qdrant

Choose one option. Both expose Qdrant on `localhost:6333`.

**Option A - Docker:**

```sh
docker run -p 6333:6333 -v ~/qdrant/storage:/qdrant/storage qdrant/qdrant
```

**Option B - Native binary on WSL (no Docker):**

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

> **WSL note:** Both options expose Qdrant on `localhost:6333` which WSL2 forwards to Windows automatically. If unreachable, run `wsl hostname -I` and use that IP instead.

---

## Starting the MCP Server

Run this in a **WSL terminal** (separate from Qdrant). Replace `myproject` with your collection name:

```sh
QDRANT_URL=http://localhost:6333 COLLECTION_NAME=myproject \
  uvx mcp-server-qdrant --transport streamable-http
```

The MCP server listens on `http://127.0.0.1:8000/mcp`.

> The collection name set here (`myproject`) is the bucket all documents are stored in. Use the same name when ingesting and when running the app.

---

## Ingesting Documents

Use the bundled `mcp-ingest` CLI (run on **Windows** in your project directory).

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

A sample standards file is provided in `examples/python_coding_standards.md`:

```sh
mcp-ingest examples/python_coding_standards.md --split-by sections --title "Python Coding Standards"
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

By default the app queries a single Qdrant MCP server. To add additional sources (Jira, Confluence, or any other MCP-compatible search tool), create a `rag.yaml` file in your project root.

A template is provided:

```sh
cp examples/rag.yaml rag.yaml
```

Edit `rag.yaml` to point each source to its MCP server:

```yaml
sources:
  default:
    mcp_url: http://localhost:8000/mcp
    mcp_tool: qdrant-find
  jira:
    mcp_url: http://localhost:9000/mcp
    mcp_tool: jira_search_issues
  confluence:
    mcp_url: http://localhost:9000/mcp
    mcp_tool: confluence_search
```

When an agent calls `RetrieveContext` with `source=jira`, it queries the Jira MCP server directly. Sources not listed in `rag.yaml` are passed as payload filters to the default Qdrant server instead.

`rag.yaml` is user-specific and excluded from version control via `.gitignore`. If absent, the app falls back to the default Qdrant server configured in `settings.py`.

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
