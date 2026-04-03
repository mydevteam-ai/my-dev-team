import argparse
import asyncio
import sys
from pathlib import Path
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession
from devteam import settings

async def _ingest(file_path: Path, source: str, title: str):
    text = file_path.read_text(encoding='utf-8')
    args = {
        'information': text,
        'metadata': {'source': source, 'title': title}
    }
    if settings.rag_collection:
        args['collection_name'] = settings.rag_collection

    async with streamable_http_client(settings.rag_mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(settings.rag_mcp_tool.replace('find', 'store'), args)

    if result.content:
        print(result.content[0].text if hasattr(result.content[0], 'text') else 'Stored.')
    else:
        print(f"Stored: {file_path}")

def main():
    parser = argparse.ArgumentParser(description='Ingest a text file into the RAG knowledge base.')
    parser.add_argument('file', help='path to the text file to ingest')
    parser.add_argument('--source', default='files', help='source tag for filtering (default: files)')
    parser.add_argument('--title', help='document title (default: file name)')
    parser.add_argument('--mcp-url', help=f'MCP server URL (default: {settings.rag_mcp_url})')
    parser.add_argument('--collection', help='Qdrant collection name (default: from settings)')
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    if args.mcp_url:
        settings.rag_mcp_url = args.mcp_url
    if args.collection:
        settings.rag_collection = args.collection

    title = args.title or file_path.name
    asyncio.run(_ingest(file_path, source=args.source, title=title))
