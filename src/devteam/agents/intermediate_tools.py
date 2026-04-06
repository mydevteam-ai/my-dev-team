from functools import cached_property
import logging
from pydantic import BaseModel
from devteam import settings
from devteam.skills import skills
from devteam.state import ProjectState
from devteam.tools import rag
from devteam.utils.workspace import read_workspace_file, list_workspace_files
from .schemas import LoadSkill, ListFiles, ReadFile, RetrieveContext
from . import schemas

class IntermediateTools:
    """Mixin to handle intermediate tool calls that are not final outputs, e.g. LoadSkill."""

    config: dict
    logger: logging.Logger

    @cached_property
    def tools(self) -> list[type[BaseModel]]:
        tools = []
        for name in self.config.get('tools', []):
            cls = getattr(schemas, name, None)
            if cls is None:
                self.logger.warning("Unknown tool '%s' in config, skipping.", name)
                continue
            if cls is RetrieveContext and not settings.rag_enabled:
                continue
            tools.append(cls)
        return tools

    async def _handle_intermediate_tools(self, tool_name: str, tool_args: dict, state: ProjectState) -> str | None:
        match tool_name:
            case LoadSkill.__name__:
                skill_names = tool_args.get('skill_names', [])
                results = []
                for name in skill_names:
                    content = skills.load_skill(name)
                    self.logger.info("Loaded skill: %s", name)
                    self.logger.debug("Skill Content:\n%s", content[:1000])
                    results.append(content)
                return '\n\n---\n\n'.join(results)
            case RetrieveContext.__name__:
                query = tool_args.get('query', '')
                source = tool_args.get('source')
                self.logger.info("Retrieving context for query: %s (source=%s)", query, source)
                chunks = await rag.retrieve_context(query, source=source)
                self.logger.debug("Retrieved context:\n%s", chunks[:500])
                return chunks
            case ReadFile.__name__:
                path = tool_args.get('path', '')
                self.logger.info("Reading workspace file: %s", path)
                return read_workspace_file(path, state.workspace_files, state.workspace_path)
            case ListFiles.__name__:
                self.logger.info("Listing workspace files")
                return list_workspace_files(state.workspace_files, state.workspace_path)
        return None
