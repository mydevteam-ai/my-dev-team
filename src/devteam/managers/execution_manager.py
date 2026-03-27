from logging import Logger
from typing import Callable
from langchain_core.messages import HumanMessage
from devteam.utils import status, tasks

class ExecutionManager:
    """Mixin for managing development tasks."""

    logger: Logger
    max_revision_count: int
    communication: Callable

    def _execution_node(self, state: dict) -> dict:
        # TODO: In this node we need to determine whether to take next task for developer, or this is a returned task, then we need to check if we exceeded the maximum revisions
        # We can come here:
        # 1) From planning node -> simply take first task for developer
        # 2) From developer node -> pass task for code review
        # 3) From reviewer node -> a) pass task to QA or b) return to developer
        # 4) From QA node -> either a) take next task or b) return to developer or c) pass to integration
        current_revision = state.get('revision_count', 0)
        if state.get('current_agent', '') == 'developer': # Case no. 2 : Developer just finished a task
            return {
                'current_agent': 'reviewer'
            }
        if not state.get('review_feedback', ''): # Case no. 2 : Weird case when no feedback from reviewer
            return {
                'current_agent': 'reviewer'
            }
        if not status.is_approved_status(review_feedback := state.get('review_feedback', '')) and current_revision < self.max_revision_count: # Case no. 3b
            instruction = (
                    "The Code Reviewer rejected your implementation. "
                    "Please read the feedback below, fix the code and use your tools to update the workspace.\n\n"
                    f"### Reviewer Feedback ###\n{review_feedback}"
                )
            return {
                'current_agent': 'developer',
                'revision_count': current_revision + 1,
                'review_feedback': '',
                'test_results': '',
                'messages': [HumanMessage(content=instruction)],
                'communication_log': self.communication(f"Revision {current_revision + 1} requested by reviewer.")
            }
        if not state.get('test_results', ''): # Case no. 3a
            return {
                'current_agent': 'qa'
            }
        if not status.is_approved_status(test_results := state.get('test_results', '')) and current_revision < self.max_revision_count: # Case no. 4b
            instruction = (
                    "The QA rejected your implementation. "
                    "Please read the feedback below, fix the code and use your tools to update the workspace.\n\n"
                    f"### QA Feedback ###\n{test_results}"
                )
            return {
                'current_agent': 'developer',
                'revision_count': current_revision + 1,
                'review_feedback': '',
                'test_results': '',
                'messages': [HumanMessage(content=instruction)],
                'communication_log': self.communication(f"Revision {current_revision + 1} requested by QA.")
            }
        return {
            'current_agent': 'officer' # Case no. 4a or 4c
        }

    def _officer_node(self, state: dict) -> dict:
        """Take next task for developer or pass to integration."""
        pending = state.get('pending_tasks', [])
        idx = state.get('current_task_index', 0)
        if idx < len(pending):
            task = pending[idx]
            t_name = task.get('task_name', f'Task {idx+1}')
            formatted_task = tasks.task_to_markdown(task, idx + 1)
            self.logger.info("Routing to task %i/%i: %s", idx + 1, len(pending), t_name)
            return {
                'current_agent': 'developer',
                'current_task': formatted_task,
                'current_task_index': idx + 1,
                'revision_count': 0, # Clear state including messages for next task
                'review_feedback': '',
                'test_results': '',
                'messages': self._cleanup_messages(state.get('messages')),
                'communication_log': self.communication(f"Task {idx + 1}: {t_name} ###")
            }
        self.logger.debug("Execution phase completed. Routing to integration.")
        return {
            'current_phase': 'integration',
            'current_agent': '',
            'current_task': '',
            'messages': self._cleanup_messages(state.get('messages'))
        }

    def _route_execution(self, state: dict) -> str:
        return state.get('current_agent', 'officer')
