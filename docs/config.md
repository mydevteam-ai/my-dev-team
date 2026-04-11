# Configuration file

`devteam` loads a `config.yaml` file on startup so you can set persistent defaults without repeating CLI flags on every run. CLI flags always take precedence over the file.

## File locations

Two locations are checked, in this order:

| Priority | Path | Purpose |
|---|---|---|
| 1 (lowest) | `~/.devteam/config.yaml` | Global user defaults |
| 2 (highest) | `./config.yaml` | Project-level overrides |

Both files are loaded if they exist - project-level values win on any key that appears in both.

To use a completely different file, pass `--settings <path>` on the command line.

## Supported keys

Keys are case-insensitive and spaces are treated as underscores, so `"LLM timeout"`, `LLM_TIMEOUT` and `llm_timeout` are all equivalent.

| Key | Type | Default | Equivalent CLI flag |
|---|---|---|---|
| `provider` | str | `ollama` | `--provider` |
| `rpm` | int | `0` | `--rpm` |
| `llm_timeout` | int | `120` | `--timeout` |
| `no_docker` | bool | `false` | `--no-docker` |
| `ask_approval` | bool | `false` | `--ask-approval` |
| `rag_enabled` | bool | `true` | `--no-rag` (inverted) |
| `rag_collection` | str | - | `--rag-collection` |
| `rag_mcp_url` | str | `http://localhost:8000/mcp` | - |
| `rag_mcp_tool` | str | `qdrant-find` | - |
| `workspace_dir` | path | `workspaces/` | - |
| `skills_dir` | path | `skills/` | `--skills` |
| `max_revision_count` | int | `3` | - |

## Example

```yaml
# ~/.devteam/config.yaml

provider: anthropic
llm_timeout: 300
rpm: 20
ask_approval: true
workspace_dir: ~/projects/devteam-workspaces
rag_collection: my-docs
max_revision_count: 5
```

With the above in place, running `devteam project.txt` is equivalent to:

```sh
devteam project.txt \
  --provider anthropic \
  --timeout 300 \
  --rpm 20 \
  --ask-approval \
  --rag-collection my-docs
```

A project-level `./config.yaml` can then override individual keys for that specific project:

```yaml
# ./config.yaml  (project root)

provider: ollama
llm_timeout: 600
```
