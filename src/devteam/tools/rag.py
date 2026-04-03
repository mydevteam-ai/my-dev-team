from devteam import settings

async def retrieve_context(query: str, source: str = None, limit: int = 5) -> str:
    """Call the RAG MCP server and return retrieved chunks as formatted text."""
    try:
        from mcp.client.streamable_http import streamablehttp_client  # pylint: disable=import-outside-toplevel
        from mcp import ClientSession  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        raise ImportError("mcp is required for RAG. Install it with: pip install mcp") from e
    args = {'query': query, 'n_results': limit}
    if source:
        args['filter'] = {'source': source}
    async with streamablehttp_client(settings.rag_mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(settings.rag_mcp_tool, args)
    if not result.content:
        return "No relevant documents found."
    return "\n\n---\n\n".join(
        item.text for item in result.content if hasattr(item, 'text') and item.text
    ) or "No relevant documents found."
