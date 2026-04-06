from logging import Logger
from .events import Event

class EventEmitter:
    """Mixin for emitting events to extensions"""

    all_extensions: list
    logger: Logger

    async def emit_event(self, event: Event, thread_id: str, **kwargs) -> dict | None:
        """Emit an event to all registered extensions."""
        method_name = f'on_{event}'
        merged = {}
        for ext in self.all_extensions:
            method = getattr(ext, method_name, None)
            if callable(method):
                try:
                    result = await method(thread_id, **kwargs)
                except Exception as e:
                    if ext.critical:
                        raise
                    self.logger.warning("Extension %s.%s raised an error: %s", type(ext).__name__, method_name, e)
                    continue
                if isinstance(result, dict):
                    merged.update(result)
                    if result.get('abort_requested'):
                        break
        return merged or None
