# RAG Knowledge Base

Agents configured with `rag: true` in their frontmatter can call a `RetrieveContext` tool to query an external knowledge base before producing their output. Retrieved chunks are injected into the conversation and the LLM re-evaluates with the new context.

The main app communicates with the knowledge base exclusively over MCP - no vector store client or embedding library is required in this project.

## Installation

```sh
pip install mcp
```

## Setup

**1. Start a vector store:**

**Option A - Docker (any platform):**

```sh
docker run -p 6333:6333 -v ~/qdrant/storage:/qdrant/storage qdrant/qdrant
```

**Option B - Native binary (WSL / Linux, no Docker):**

```sh
# Download and extract the binary
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-musl.tar.gz | tar -xz -C ~/qdrant

# Create a config file so Qdrant knows where to store data
mkdir -p ~/qdrant/storage
cat > ~/qdrant/config.yaml << 'EOF'
storage:
  storage_path: ./storage
EOF

# Run Qdrant (keep this terminal open, or run it as a background service)
cd ~/qdrant && ./qdrant
```

> **WSL note:** Qdrant listens on `0.0.0.0:6333`, which WSL2 automatically forwards to `localhost:6333` on the Windows host. If the port is not reachable from Windows, run `wsl hostname -I` to get the WSL IP and use that instead.

**2. Install `uv` (provides `uvx`, required for the MCP server):**

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env # or restart your shell
```

**3. Start the MCP server:**

Replace `myproject` with your desired collection name:

```sh
QDRANT_URL=http://localhost:6333 COLLECTION_NAME=myproject uvx mcp-server-qdrant --transport streamable-http
```

The server listens on `http://127.0.0.1:8000/mcp` by default.

**4. Ingest documents:**

Use the bundled `mcp-ingest` CLI to add text files to the knowledge base:

```sh
mcp-ingest path/to/document.txt
mcp-ingest path/to/document.txt --title "Python Coding Standards" --source files
```

A sample standards file is available at `examples/python_coding_standards.txt`.

**5. Verify documents are stored:**

```sh
curl -s http://localhost:6333/collections/myproject/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "with_payload": true}' | python3 -m json.tool
```

## Configuration

The MCP server URL and tool name can be overridden in `settings.py`:

```python
settings.rag_mcp_url = 'http://localhost:8000/mcp'   # default
settings.rag_mcp_tool = 'qdrant-find'            # default
```

## Enabling RAG per agent

Add `rag: true` to the agent's `.md` frontmatter:

```yaml
---
role: Product Manager
capabilities: [reasoning]
temperature: 0.4
rag: true
---
```

Remove the flag to disable RAG for that agent. No Python code changes are needed.
