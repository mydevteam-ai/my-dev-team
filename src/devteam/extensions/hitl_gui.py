import asyncio
import threading
import time
from queue import Queue
from langchain_core.messages import HumanMessage
from devteam import settings
from .base_extension import CrewExtension

_SYSTEM_NODES = frozenset({'manager', 'officer', 'human', '__interrupt__'})
_DEVELOPMENT_AGENTS = frozenset({'developer', 'reviewer', 'qa', 'judge', 'developer_a', 'developer_b', 'migrator', 'equivalence_checker'})

class HumanInTheLoopGUI(CrewExtension):
    """Extension that pauses the workflow to get human input via the Streamlit GUI."""

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self._response_event = threading.Event()
        self._response: str | None = None
        self._aborted = False
        self._last_agent: str = ''

    def submit_response(self, response: str):
        """Called from the GUI when the user submits their answer."""
        self._response = response
        self._aborted = False
        self._response_event.set()

    def abort(self):
        """Called from the GUI when the user wants to abort."""
        self._response = None
        self._aborted = True
        self._response_event.set()

    async def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        for node_name in state_update:
            if node_name not in _SYSTEM_NODES:
                self._last_agent = node_name

    async def on_pause(self, thread_id: str, current_state: dict, next_node: str) -> dict | None:
        if next_node == 'manager' and settings.ask_all:
            return await self._request_agent_approval(thread_id, self._last_agent, current_state)
        if next_node != 'human':
            return None
        if current_state.get('clarification_question'):
            return await self._request_clarification(thread_id, current_state)
        if current_state.get('specs'):
            return await self._request_approval(thread_id, current_state)
        return None

    async def _request_agent_approval(self, thread_id: str, agent: str, current_state: dict) -> dict | None:
        task_context = current_state.get('task_context')
        task_name = getattr(task_context, 'current_task_name', '') if task_context else ''
        self.event_queue.put({
            'type': 'hitl_request',
            'mode': 'approval_agent',
            'thread_id': thread_id,
            'agent': agent,
            'task_name': task_name,
            'ts': time.time(),
        })
        self._response_event.clear()
        await asyncio.to_thread(self._response_event.wait)
        if self._aborted:
            return {
                'abort_requested': True,
                'communication_log': self.communication(f"Aborted after {agent}.")
            }
        if self._response == 'approved':
            return {'communication_log': self.communication(f"Approved: {agent}.")}
        return self._build_feedback_update(agent, self._response, current_state)

    def _build_feedback_update(self, agent: str, feedback: str, current_state: dict) -> dict:
        if agent in _DEVELOPMENT_AGENTS:
            task_context = current_state.get('task_context')
            if task_context:
                return {
                    'task_context': task_context.model_copy(update={'human_feedback': feedback}),
                    'communication_log': self.communication(f"Human feedback to {agent}: {feedback}")
                }
        if agent == 'pm':
            return {
                'specs': '',
                'specs_approved': False,
                'messages': [HumanMessage(content=f"The user rejected the specifications. Feedback: {feedback}")],
                'communication_log': self.communication(f"Specification rework requested: {feedback}")
            }
        if agent in ('architect', 'analyzer'):
            return {
                'pending_tasks': [],
                'tasks_approved': False,
                'messages': [HumanMessage(content=f"The user rejected the task plan. Feedback: {feedback}")],
                'communication_log': self.communication(f"Task plan rework requested: {feedback}")
            }
        return {'communication_log': self.communication(f"Note after {agent}: {feedback}")}

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
