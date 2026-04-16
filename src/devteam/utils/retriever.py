import re
from pathlib import Path
from rank_bm25 import BM25Okapi
from .sanitizer import sanitize_for_prompt
from .workspace import live_paths

_SPLIT_RE = re.compile(r'[^a-zA-Z0-9]+')
_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, expanding camelCase and snake_case identifiers."""
    expanded = _CAMEL_RE.sub(' ', text)
    tokens = _SPLIT_RE.split(expanded.lower())
    return [t for t in tokens if len(t) >= 2]


def _read_documents(workspace_path: str) -> list[tuple[str, str]]:
    """Read all workspace files into (path, content) pairs."""
    root = Path(workspace_path)
    documents: list[tuple[str, str]] = []
    for rel_path in sorted(live_paths(workspace_path)):
        try:
            content = (root / rel_path).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        documents.append((rel_path, content))
    return documents


def _format_files(files: list[tuple[str, str]]) -> str:
    """Format file pairs as '--- FILE: path ---\\ncontent' blocks."""
    parts = []
    for path, content in files:
        clean = sanitize_for_prompt(content, [path, 'workspace'])
        parts.append(f"--- FILE: {path} ---\n{clean}")
    return '\n\n'.join(parts)


def retrieve_workspace_context(workspace_path: str, query: str, top_k: int = 10) -> str:
    """Retrieve the most relevant workspace files for a query using BM25 ranking."""
    documents = _read_documents(workspace_path)
    if not documents:
        return "No files exist in the workspace."
    if len(documents) <= top_k or not query.strip():
        return _format_files(documents)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return _format_files(documents)

    corpus = [_tokenize(f"{path} {content}") for path, content in documents]
    scores = BM25Okapi(corpus).get_scores(query_tokens)
    ranked = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)

    sections: list[str] = []
    sections.append("## Relevant workspace files (retrieved content)\n\n"
                     + _format_files([documents[i] for i in ranked[:top_k]]))

    if other_paths := sorted(documents[i][0] for i in ranked[top_k:]):
        listing = '\n'.join(f"- {p}" for p in other_paths)
        sections.append(
            f"## Other workspace files ({len(other_paths)}) - paths only\n\n"
            f"Use ReadFile, GlobFiles or GrepFiles to access these if needed.\n\n{listing}"
        )
    return '\n\n'.join(sections)


def _rank_items(items: list[str], query: str, top_k: int) -> list[int]:
    """Return indices of the top_k most relevant items for the query."""
    corpus = [_tokenize(item) for item in items]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return list(range(min(top_k, len(items))))
    scores = BM25Okapi(corpus).get_scores(query_tokens)
    return sorted(range(len(items)), key=lambda i: scores[i], reverse=True)[:top_k]


def retrieve_skills_context(catalog: list[dict], query: str, top_k: int = 5) -> str:
    """Retrieve the most relevant skills from the catalog using BM25 ranking.

    Each catalog entry has 'name' and 'description' keys.
    Returns a formatted list with relevant skills first and remaining skills listed separately.
    """
    if not catalog:
        return "No skills available."
    if len(catalog) <= top_k or not query.strip():
        return _format_skills(catalog)

    items = [f"{s['name']} {s['description']}" for s in catalog]
    ranked = _rank_items(items, query, top_k)
    top_set = set(ranked)

    sections: list[str] = []
    relevant = [catalog[i] for i in ranked]
    sections.append("## Relevant skills\n\n" + _format_skills(relevant))

    others = [catalog[i] for i in range(len(catalog)) if i not in top_set]
    if others:
        listing = _format_skills(others)
        sections.append(f"## Other available skills ({len(others)})\n\n{listing}")

    return '\n\n'.join(sections)


def _format_skills(catalog: list[dict]) -> str:
    """Format skill catalog entries as a bullet list."""
    return '\n'.join(f"- `{s['name']}`: {s['description']}" for s in catalog)
