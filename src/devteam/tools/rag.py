import functools
import yaml
from pathlib import Path
from devteam import settings


@functools.lru_cache(maxsize=1)
def _load_sources() -> dict:
    rag_config = Path('rag.yaml')
    if not rag_config.exists():
        return {}
    with open(rag_config, encoding='utf-8') as f:
        return yaml.safe_load(f).get('sources', {})


@functools.lru_cache(maxsize=8)
def _resolve_source(source: str | None) -> tuple[str, str, dict]:
    """Return (mcp_url, mcp_tool, extra_args) for the given source."""
    all_sources = _load_sources()
    if source and source in all_sources:
        cfg = all_sources[source]
        return cfg['mcp_url'], cfg['mcp_tool'], {}
    default = all_sources.get('default', {})
    mcp_url = default.get('mcp_url', settings.rag_mcp_url)
    mcp_tool = default.get('mcp_tool', settings.rag_mcp_tool)
    extra_args = {'filter': {'source': source}} if source else {}
    return mcp_url, mcp_tool, extra_args


async def retrieve_context(query: str, source: str | None = None) -> str:
    """Call the appropriate RAG MCP server and return retrieved chunks as formatted text."""
    try:
        # pylint: disable=import-outside-toplevel
        from mcp.client.streamable_http import streamable_http_client
        from mcp import ClientSession
    except ImportError as e:
        raise ImportError("mcp is required for RAG. Install it with: pip install mcp") from e

    mcp_url, mcp_tool, extra_args = _resolve_source(source)

    args = {'query': query, **extra_args}
    if settings.rag_collection and mcp_tool == 'qdrant-find':
        args['collection_name'] = settings.rag_collection

    try:
        async with streamable_http_client(mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(mcp_tool, args)
    except Exception as e:
        return f"Knowledge base unavailable ({e.__class__.__name__}). Proceed without retrieved context."

    if not result.content:
        return "No relevant documents found."
    return "\n\n---\n\n".join(
        item.text for item in result.content if hasattr(item, 'text') and item.text
    ) or "No relevant documents found."
