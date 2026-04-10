import logging
from collections.abc import Awaitable, Callable
from pydantic import BaseModel
from devteam.skills import skills
from devteam.state import ProjectState
from devteam.tools import rag
from devteam.tools.schemas import LoadSkill, ReadFile, ListFiles, GlobFiles, GrepFiles, RetrieveContext
from devteam.utils.workspace import read_workspace_file, list_workspace_files, glob_workspace_files, grep_workspace_files

type ToolHandler = Callable[[dict, ProjectState, logging.Logger], Awaitable[str]]

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry mapping tool names to their Pydantic schema and async handler."""

    def __init__(self):
        self._entries: dict[str, tuple[type[BaseModel], ToolHandler]] = {}

    def register(self, name: str, schema: type[BaseModel], handler: ToolHandler):
        self._entries[name] = (schema, handler)

    def get_schema(self, name: str) -> type[BaseModel]:
        entry = self._entries.get(name)
        return entry[0] if entry else None

    def get_handler(self, name: str) -> ToolHandler:
        entry = self._entries.get(name)
        return entry[1] if entry else None

    def __contains__(self, name: str) -> bool:
        return name in self._entries

tool_registry = ToolRegistry()


async def _handle_load_skill(tool_args: dict, _state: ProjectState, _logger: logging.Logger) -> str:
    skill_names = tool_args.get('skill_names', [])
    results = []
    for name in skill_names:
        content = skills.load_skill(name)
        _logger.info("Loaded skill: %s", name)
        _logger.debug("Skill Content:\n%s", content[:1000])
        results.append(content)
    return '\n\n---\n\n'.join(results)


async def _handle_retrieve_context(tool_args: dict, _state: ProjectState, _logger: logging.Logger) -> str:
    query = tool_args.get('query', '')
    source = tool_args.get('source')
    _logger.info("Retrieving context for query: %s (source=%s)", query, source)
    chunks = await rag.retrieve_context(query, source=source)
    _logger.debug("Retrieved context:\n%s", chunks[:500])
    return chunks


async def _handle_read_file(tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    path = tool_args.get('path', '')
    _logger.info("Reading workspace file: %s", path)
    return read_workspace_file(path, state.workspace_path)


async def _handle_list_files(_tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    _logger.info("Listing workspace files")
    return list_workspace_files(state.workspace_path)


async def _handle_glob_files(tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    pattern = tool_args.get('pattern', '*')
    _logger.info("Glob workspace files: %s", pattern)
    return glob_workspace_files(pattern, state.workspace_path)


async def _handle_grep_files(tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    pattern = tool_args.get('pattern', '')
    glob_filter = tool_args.get('glob')
    _logger.info("Grep workspace files: %s (glob=%s)", pattern, glob_filter)
    return grep_workspace_files(pattern, state.workspace_path, glob_filter=glob_filter)


def _register_builtins():
    tool_registry.register(LoadSkill.__name__, LoadSkill, _handle_load_skill)
    tool_registry.register(RetrieveContext.__name__, RetrieveContext, _handle_retrieve_context)
    tool_registry.register(ReadFile.__name__, ReadFile, _handle_read_file)
    tool_registry.register(ListFiles.__name__, ListFiles, _handle_list_files)
    tool_registry.register(GlobFiles.__name__, GlobFiles, _handle_glob_files)
    tool_registry.register(GrepFiles.__name__, GrepFiles, _handle_grep_files)


_register_builtins()
