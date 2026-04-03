import argparse
import asyncio
import re
import sys
from pathlib import Path
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession
from devteam import settings

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64


def _chunk_by_words(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(' '.join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _chunk_by_sections(text: str) -> list[str]:
    parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    if parts and not parts[0].startswith('## ') and len(parts) > 1:
        parts[1] = parts[0] + '\n\n' + parts[1]
        parts = parts[1:]
    return parts


async def _store_chunk(session: ClientSession, text: str, metadata: dict):
    args = {'information': text, 'metadata': metadata}
    if settings.rag_collection:
        args['collection_name'] = settings.rag_collection
    await session.call_tool(settings.rag_mcp_tool.replace('find', 'store'), args)


async def _ingest(file_path: Path, source: str, title: str, chunk_size: int, overlap: int, split_by: str):
    text = file_path.read_text(encoding='utf-8')

    if chunk_size == 0:
        chunks = None
    elif split_by == 'sections':
        chunks = _chunk_by_sections(text)
    else:
        chunks = _chunk_by_words(text, chunk_size, overlap)

    async with streamable_http_client(settings.rag_mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if not chunks or len(chunks) <= 1:
                await _store_chunk(session, text, {'source': source, 'title': title})
                print(f"Stored: {file_path} (1 chunk)")
            else:
                total = len(chunks)
                for i, chunk in enumerate(chunks, 1):
                    metadata = {'source': source, 'title': title, 'chunk': i, 'total_chunks': total}
                    await _store_chunk(session, chunk, metadata)
                    print(f"Stored chunk {i}/{total}", end='\r')
                print(f"Stored: {file_path} ({total} chunks, split-by={split_by})")


def main():
    parser = argparse.ArgumentParser(description='Ingest a text file into the RAG knowledge base.')
    parser.add_argument('file', help='path to the text file to ingest')
    parser.add_argument('--source', default='files', help='source tag for filtering (default: files)')
    parser.add_argument('--title', help='document title (default: file name)')
    parser.add_argument('--mcp-url', help=f'MCP server URL (default: {settings.rag_mcp_url})')
    parser.add_argument('--collection', help='collection name (default: from settings)')
    splitting = parser.add_mutually_exclusive_group()
    splitting.add_argument('--no-split', action='store_true', help='store the entire document as a single chunk without splitting')
    splitting.add_argument('--split-by', choices=['words', 'sections'], default='words', help='chunking strategy: words (default) or sections (Markdown headings)')
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE, help=f'chunk size in words, used when --split-by=words (default: {DEFAULT_CHUNK_SIZE})')
    parser.add_argument('--overlap', type=int, default=DEFAULT_CHUNK_OVERLAP, help=f'overlap in words between chunks, used when --split-by=words (default: {DEFAULT_CHUNK_OVERLAP})')
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
    chunk_size = 0 if args.no_split else args.chunk_size
    asyncio.run(_ingest(file_path, source=args.source, title=title, chunk_size=chunk_size, overlap=args.overlap, split_by=args.split_by))
