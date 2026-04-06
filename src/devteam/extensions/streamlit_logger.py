import time
from typing import override
from queue import Queue
from devteam.crew.events import Event
from .base_extension import CrewExtension

class StreamlitLogger(CrewExtension):
    """Extension to publish execution events to a thread-safe queue"""

    def __init__(self, event_queue: Queue):
        self.queue = event_queue

    def _emit(self, event_type: Event, **data):
        self.logger.debug("Emitting event: %s", event_type)
        self.queue.put({
            'type': event_type,
            'ts': time.time(),
            **data,
        })

    @override
    async def on_start(self, thread_id: str, initial_state: dict):
        self._emit('start', thread_id=thread_id, state=initial_state)

    @override
    async def on_resume(self, thread_id: str, state_update: dict):
        self._emit('resume', thread_id=thread_id, state_update=state_update)

    @override
    async def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        self._emit('step', thread_id=thread_id,
                   state_update=state_update, full_state=full_state)

    @override
    async def on_pause(self, thread_id: str, current_state: dict, next_node: str) -> dict | None:
        self._emit('pause', thread_id=thread_id, next_node=next_node)
        return None  # Streamlit handles HITL via its own UI

    @override
    async def on_finish(self, thread_id: str, final_state: dict):
        if final_state.get('error'):
            self._emit('error', thread_id=thread_id, state=final_state)
        else:
            self._emit('finish', thread_id=thread_id, state=final_state)
