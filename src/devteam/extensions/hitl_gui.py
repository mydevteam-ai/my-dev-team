import asyncio
import threading
import time
from queue import Queue
from langchain_core.messages import HumanMessage
from .base_extension import CrewExtension

class HumanInTheLoopGUI(CrewExtension):
    """Extension that pauses the workflow to get human input via the Streamlit GUI."""

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self._response_event = threading.Event()
        self._response: str | None = None
        self._aborted = False

    def submit_response(self, response: str):
        """Called from the Streamlit UI when the user submits their answer."""
        self._response = response
        self._aborted = False
        self._response_event.set()

    def abort(self):
        """Called from the Streamlit UI when the user wants to abort."""
        self._response = None
        self._aborted = True
        self._response_event.set()

    async def on_pause(self, thread_id: str, current_state: dict, next_node: str) -> dict | None:
        if next_node != 'human':
            return None
        if current_state.get('clarification_question'):
            return await self._request_clarification(thread_id, current_state)
        if current_state.get('specs'):
            return await self._request_approval(thread_id, current_state)
        return None

    async def _request_clarification(self, thread_id: str, current_state: dict) -> dict | None:
        self.event_queue.put({
            'type': 'hitl_request',
            'mode': 'clarification',
            'thread_id': thread_id,
            'question': current_state.get('clarification_question', 'The team needs your input.'),
            'ts': time.time(),
        })
        self._response_event.clear()
        await asyncio.to_thread(self._response_event.wait)
        if self._aborted:
            return {
                'abort_requested': True,
                'communication_log': self.communication("Aborted the workflow.")
            }
        return {
            'messages': [HumanMessage(content=self._response)],
            'communication_log': self.communication(self._response)
        }

    async def _request_approval(self, thread_id: str, current_state: dict) -> dict | None:
        pending_tasks = current_state.get('pending_tasks', [])
        mode = 'approval_plan' if pending_tasks else 'approval_spec'
        self.event_queue.put({
            'type': 'hitl_request',
            'mode': mode,
            'thread_id': thread_id,
            'specs': current_state.get('specs', ''),
            'pending_tasks': pending_tasks,
            'ts': time.time(),
        })
        self._response_event.clear()
        await asyncio.to_thread(self._response_event.wait)
        if self._aborted:
            return {
                'abort_requested': True,
                'communication_log': self.communication("Aborted during plan approval.")
            }
        if self._response == 'approved':
            if mode == 'approval_spec':
                return {
                    'specs_approved': True,
                    'communication_log': self.communication("Specifications approved by user.")
                }
            return {
                'current_phase': 'development',
                'tasks_approved': True,
                'communication_log': self.communication("Task plan approved by user.")
            }
        # Rework feedback
        if mode == 'approval_spec':
            return {
                'specs': '',
                'specs_approved': False,
                'messages': [HumanMessage(content=f"Specification feedback from user: {self._response}")],
                'communication_log': self.communication(f"Specification rework requested: {self._response}")
            }
        return {
            'pending_tasks': [],
            'messages': [HumanMessage(content=f"Task plan feedback from user: {self._response}")],
            'communication_log': self.communication(f"Task plan rework requested: {self._response}")
        }
