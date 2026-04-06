from functools import cached_property
import logging
from pydantic import BaseModel
from devteam import settings
from devteam.state import ProjectState
from devteam.tools.registry import tool_registry
from . import schemas


class IntermediateTools:
    """Mixin that resolves tool schemas from config and dispatches intermediate tool calls via the registry."""

    config: dict
    logger: logging.Logger

    @cached_property
    def tools(self) -> list[type[BaseModel]]:
        tools = []
        for name in self.config.get('tools', []):
            schema = tool_registry.get_schema(name) or getattr(schemas, name, None)
            if schema is None:
                self.logger.warning("Unknown tool '%s' in config, skipping.", name)
                continue
            if name == 'RetrieveContext' and not settings.rag_enabled:
                continue
            tools.append(schema)
        return tools

    async def _handle_intermediate_tools(self, tool_name: str, tool_args: dict, state: ProjectState) -> str:
        handler = tool_registry.get_handler(tool_name)
        if handler is None:
            return None
        return await handler(tool_args, state, self.logger)
