# Examples

All examples live in the `examples/` folder. Each one is a ready-to-run project file (or folder) that demonstrates a specific feature of My Dev Team.

---

## Development workflow examples

### Hello World (`hello_world_python.txt`)

The simplest possible project file. One sentence of requirements. Good for verifying that installation and LLM connectivity work before trying anything more complex.

```sh
devteam examples/hello_world_python.txt
```

---

### Calculator - clear requirements (`calc_app_python.txt`)

A well-specified Python CLI calculator. The Product Manager receives enough detail to write specs without asking clarifying questions, so the workflow runs straight through to code.

Demonstrates: standard planning - development - integration pipeline.

```sh
devteam examples/calc_app_python.txt
```

---

### Calculator - vague requirements (`vague_reqs_python.txt`)

The same calculator, but requirements are deliberately minimal ("Develop a calculator application in Python."). The Product Manager will ask at least one clarifying question before writing specs.

Demonstrates: the HITL clarification loop - the workflow pauses at the `human` node and waits for your answer before continuing.

```sh
devteam examples/vague_reqs_python.txt
```

---

### Calculator - seeded workspace (`calc_app_python_seed.txt`)

The calculator brief with a `--seed` pointing at `examples/calc_app/`. The workspace is pre-populated with a partially written `calc.py` and `test_calc.py` before the agents start. The Developer is instructed to read existing files before modifying them.

Demonstrates: `--seed` for building on top of existing code.

```sh
devteam examples/calc_app_python_seed.txt --seed examples/calc_app
```

---

### Bookstore - BM25 retrieval tuning (`bookstore_retrieval_demo.txt`)

A realistic 30-file Flask + SQLAlchemy bookstore backend (auth, models, api, services, utils, tests) paired with a focused task brief asking the crew to rate-limit the login endpoints against brute-force attacks. The codebase is large enough that BM25 top-k=10 meaningfully filters, and the task is narrow enough that the expected relevant files (`src/auth/*`, `src/api/auth_routes.py`, `tests/test_auth.py`) are predictable.

Demonstrates: the `workspace_context` / `skills_context` retrieval flow in practice - task-scoped agents (QA, Equivalence Checker, Migrator) receive only relevant files in full, with the rest listed as paths for on-demand reading.

```sh
devteam examples/bookstore_retrieval_demo.txt --provider anthropic --seed examples/bookstore_flask
```

**Tuning the retriever:** `examples/retrieval_demo_preview.py` is a standalone harness that runs the same BM25 ranker against `examples/bookstore_flask/` without spinning up the full crew. It ships with five labelled queries plus expected-file sets and prints `precision@k` so you can measure the impact of tokenization or parameter changes on ranking quality.

```sh
python examples/retrieval_demo_preview.py
python examples/retrieval_demo_preview.py --top-k 5
python examples/retrieval_demo_preview.py --query "add two-factor enrollment endpoint"
```

---

### Calculator - RAG-augmented (`calc_app_python_rag.txt`)

The same calculator brief with an instruction forcing the Product Manager to call `RetrieveContext` before writing specs. Requires a running RAG MCP server and a knowledge base with ingested documents (e.g. the `examples/rag/python_coding_standards.md` file).

Demonstrates: RAG context retrieval - agents querying an external knowledge base to apply project-specific standards.

```sh
# 1. Start the RAG stack (Qdrant + MCP server)
# 2. Ingest the coding standards
vectorize-me examples/rag/python_coding_standards.md --source files

# 3. Run with RAG enabled
devteam examples/calc_app_python_rag.txt --provider ollama --rag-collection my-collection
```

---

## Migration workflow examples

### COBOL Payroll - migrate to Python (`cobol_payroll/`)

A realistic COBOL weekly payroll calculator (`PAYROLL.cbl`) with five employee records (`employees.dat`). The migration brief (`migrate_to_python.txt`) instructs the crew to produce idiomatic Python 3.12 preserving all business logic: overtime calculation, three tax brackets, fixed-width record parsing and a formatted report.

Demonstrates: `--workflow migration` - CodeAnalyzer decomposes the COBOL program into a parallel task backlog, Migrator translates each paragraph group, EquivalenceChecker verifies behavioral equivalence.

**Source structure:**

```
examples/cobol_payroll/
- src/PAYROLL.cbl          # COBOL source (paragraphs, WORKING-STORAGE, EVALUATE)
- employees.dat            # Fixed-width input records (5 employees)
cobol_to_python.txt        # Migration brief - pass this to devteam
```

**Key COBOL constructs the crew must translate:**

| COBOL | Python equivalent |
| --- | --- |
| `WORKING-STORAGE` group items | dataclass fields |
| `PIC 9(n)V99` numeric PIC | `decimal.Decimal` |
| `EVALUATE TRUE / WHEN` | `match`/`case` or `if`/`elif` |
| `PERFORM ... UNTIL` | `while` loop |
| `FD` / `OPEN` / `READ AT END` | `open()` + iteration |
| `MULTIPLY x BY y GIVING z ROUNDED` | `round(x * y, 2)` |

```sh
devteam examples/cobol_to_python.txt --workflow migration --seed examples/cobol_payroll --provider anthropic
```

---

## Supporting files

### `examples/rag/python_coding_standards.md`

A sample coding standards document. Ingest it into your RAG knowledge base and use it with `calc_app_python_rag.txt` to see agents applying project-specific conventions.

### `examples/rag/rag.yaml`

A template RAG source configuration. Copy it to your project root and adjust the MCP server URLs to match your setup. See [RAG documentation](rag.md) for full setup instructions.

### `examples/skills/python-expert/`

A sample SKILL that injects Python best-practice instructions (PEP 8, docstrings, error handling) into any agent that loads it. Pass `--skills examples/skills` to activate it.

```sh
devteam examples/calc_app_python.txt --skills examples/skills
```
