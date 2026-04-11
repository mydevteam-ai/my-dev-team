# Welcome to My Dev Team 🚀

**My Dev Team** is an autonomous, LangGraph-powered AI development agency. It takes raw project requirements and processes them through a multi-agent workflow to incrementally build, test and deliver production-ready code.

## Why My Dev Team?

Unlike third-party SaaS platforms, **My Dev Team** is a local-first orchestrator. Your workspace, SQLite state database and review trails live 100% on your machine.

* **Privacy-Focused:** Your proprietary codebase is never stored on external platform servers.
* **Zero Egress Options:** Run the entire crew locally for free using **Ollama**.
* **Self-Healing Code:** Agents (Developer, Reviewer and QA) continuously loop until unit tests pass and code meets specifications.
* **Resilient State:** Powered by asynchronous SQLite checkpointing. Resume any thread instantly after interruptions or rate limits.

## Workflows

### Development (default)

The standard greenfield workflow. Takes raw requirements and builds production-ready code end-to-end.

| Agent | Responsibility |
| --- | --- |
| **Product Manager** | Analyzes requirements and writes Technical Specifications. |
| **System Architect** | Breaks specifications into a backlog of developer tasks. |
| **Senior Developer** | Writes implementation code and unit tests. |
| **Code Reviewer** | Reviews code for correctness, style and spec compliance. |
| **QA Engineer** | Validates code using LLM simulation or a secure Docker sandbox. |
| **Reporter** | Generates a final Markdown report of the entire build. |

```sh
devteam project.txt --provider anthropic
```

### Migration

Migrates an existing codebase to a different language (e.g. COBOL to Java, PL/SQL to Python). Point it at your legacy source tree with `--seed`.

| Agent | Responsibility |
| --- | --- |
| **Code Analyzer** | Reads source workspace, maps constructs to target idioms, produces task backlog. |
| **Migrator** | Translates one source unit at a time, writes idiomatic target code and equivalence tests. |
| **Code Reviewer** | Reviews translated code for correctness and style. |
| **Equivalence Checker** | Verifies behavioral equivalence against original source logic. |
| **Reporter** | Generates a final migration report. |

```sh
devteam migration-brief.txt --workflow migration --seed ./legacy-cobol --provider anthropic
```

## Quick Start

Ready to build?
1.  **[Install](installation.md)** the package via pip.
2.  Create a `project.txt` with your requirements.
3.  Run `devteam project.txt` in your terminal.

---
*Distributed under the Apache 2.0 license.*
