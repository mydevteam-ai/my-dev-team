# Welcome to My Dev Team 🚀

**My Dev Team** is an autonomous, LangGraph-powered AI development agency. It takes raw project requirements and processes them through a multi-agent workflow to incrementally build, test and deliver production-ready code.

## Why My Dev Team?

Unlike third-party SaaS platforms, **My Dev Team** is a local-first orchestrator. Your workspace, SQLite state database and review trails live 100% on your machine.

* **Privacy-Focused:** Your proprietary codebase is never stored on external platform servers.
* **Zero Egress Options:** Run the entire crew locally for free using **Ollama**.
* **Self-Healing Code:** Agents (Developer, Reviewer and QA) continuously loop until unit tests pass and code meets specifications.
* **Resilient State:** Powered by asynchronous SQLite checkpointing. Resume any thread instantly after interruptions or rate limits.

## The AI Crew

The agency consists of specialized agents handling distinct phases of the software development lifecycle:

| Agent | Responsibility |
| :--- | :--- |
| **Product Manager** | Analyzes requirements and writes Technical Specifications. |
| **System Architect** | Breaks specifications into a backlog of developer tasks. |
| **Senior Developer** | Writes implementation code and unit tests. |
| **QA Engineer** | Validates code using LLM simulation or a secure Docker sandbox. |
| **Reporter** | Generates a final Markdown report of the entire build. |

## Quick Start

Ready to build?
1.  **[Install](installation.md)** the package via pip.
2.  Create a `project.txt` with your requirements.
3.  Run `devteam project.txt` in your terminal.

---
*Distributed under the Apache 2.0 license.*
