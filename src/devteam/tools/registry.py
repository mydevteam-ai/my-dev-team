import logging
from collections.abc import Awaitable, Callable
from pydantic import BaseModel
from devteam.state import ProjectState
from devteam.agents.schemas import LoadSkill, ReadFile, ListFiles, RetrieveContext

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
    from devteam.skills import skills  # pylint: disable=import-outside-toplevel
    skill_names = tool_args.get('skill_names', [])
    results = []
    for name in skill_names:
        content = skills.load_skill(name)
        _logger.info("Loaded skill: %s", name)
        _logger.debug("Skill Content:\n%s", content[:1000])
        results.append(content)
    return '\n\n---\n\n'.join(results)


async def _handle_retrieve_context(tool_args: dict, _state: ProjectState, _logger: logging.Logger) -> str:
    from devteam.tools import rag  # pylint: disable=import-outside-toplevel
    query = tool_args.get('query', '')
    source = tool_args.get('source')
    _logger.info("Retrieving context for query: %s (source=%s)", query, source)
    chunks = await rag.retrieve_context(query, source=source)
    _logger.debug("Retrieved context:\n%s", chunks[:500])
    return chunks


async def _handle_read_file(tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    from devteam.utils.workspace import read_workspace_file  # pylint: disable=import-outside-toplevel
    path = tool_args.get('path', '')
    _logger.info("Reading workspace file: %s", path)
    return read_workspace_file(path, state.workspace_files, state.workspace_path)


async def _handle_list_files(_tool_args: dict, state: ProjectState, _logger: logging.Logger) -> str:
    from devteam.utils.workspace import list_workspace_files  # pylint: disable=import-outside-toplevel
    _logger.info("Listing workspace files")
    return list_workspace_files(state.workspace_files, state.workspace_path)


def _register_builtins():
    tool_registry.register(LoadSkill.__name__, LoadSkill, _handle_load_skill)
    tool_registry.register(RetrieveContext.__name__, RetrieveContext, _handle_retrieve_context)
    tool_registry.register(ReadFile.__name__, ReadFile, _handle_read_file)
    tool_registry.register(ListFiles.__name__, ListFiles, _handle_list_files)


_register_builtins()
