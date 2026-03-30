from logging import Logger
from typing import Callable
from langchain_core.messages import HumanMessage
from devteam.state import ProjectState, PendingTask
from devteam.utils import status, tasks

class ExecutionManager:
    """Mixin for managing development tasks."""

    logger: Logger
    max_revision_count: int
    communication: Callable

    def _find_next_task(self, state: ProjectState) -> PendingTask | None:
        """Return the first task whose dependencies are met and hasn't been started yet."""
        completed = set(state.completed_tasks)
        return next(
            (task for task in state.pending_tasks
             if task['task_name'] not in completed
             and all(dep in completed for dep in task.get('dependencies', []))),
            None,
        )

    def _execution_node(self, state: ProjectState) -> dict:
        # We can come here:
        # 1) From planning node -> officer will pick up first ready tasks
        # 2) From developer node -> pass task for code review
        # 3) From reviewer node -> a) pass task to QA or b) return to developer
        # 4) From QA node -> either a) task complete or b) return to developer
        current_revision = state.revision_count
        if state.current_agent == 'developer': # Case no. 2
            return {
                'current_agent': 'reviewer'
            }
        if not state.review_feedback: # Case no. 3: reviewer hasn't run yet
            return {
                'current_agent': 'reviewer'
            }
        if not status.is_approved(state.review_feedback):
            if current_revision < self.max_revision_count: # Case no. 3b: rejected, retry
                instruction = (
                        "The Code Reviewer rejected your implementation. "
                        "Please read the feedback below, fix the code and use your tools to update the workspace.\n\n"
                        f"### Reviewer Feedback ###\n{state.review_feedback}"
                    )
                return {
                    'current_agent': 'developer',
                    'revision_count': current_revision + 1,
                    'review_feedback': '',
                    'test_results': '',
                    'messages': [HumanMessage(content=instruction)],
                    'communication_log': self.communication(f"Revision {current_revision + 1} requested by reviewer.")
                }
            self.logger.warning("Max revisions reached with a rejected review. Running QA on best attempt.")
            return {
                'current_agent': 'qa'
            }
        if not state.test_results: # Case no. 3a: review approved, send to QA
            return {
                'current_agent': 'qa'
            }
        if not status.is_approved(state.test_results) and current_revision < self.max_revision_count: # Case no. 4b
            instruction = (
                    "The QA rejected your implementation. "
                    "Please read the feedback below, fix the code and use your tools to update the workspace.\n\n"
                    f"### QA Feedback ###\n{state.test_results}"
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
            'current_agent': 'officer',
            'completed_tasks': [state.current_task_name],
        }

    def _officer_node(self, state: ProjectState) -> dict:
        """Find the next ready task and set it up or transition to integration."""
        self.logger.debug(
            "Officer state - completed: %s | pending: %s",
            state.completed_tasks,
            [t['task_name'] for t in state.pending_tasks],
        )
        task = self._find_next_task(state)

        if not task:
            all_names = {t['task_name'] for t in state.pending_tasks}
            if not (all_names <= set(state.completed_tasks)):
                self.logger.warning(
                    "Officer: no ready tasks but %d incomplete (dependency deadlock?). Proceeding to integration.",
                    len(all_names - set(state.completed_tasks)),
                )
            self.logger.debug("All tasks complete. Routing to integration.")
            return {
                'current_phase': 'integration',
                'current_agent': '',
                'current_task': '',
                'current_task_name': '',
                'test_results': '',
                'messages': self._cleanup_messages(state.messages),
            }

        task_idx = next(
            (i + 1 for i, t in enumerate(state.pending_tasks) if t['task_name'] == task['task_name']), 1
        )
        formatted = tasks.task_to_markdown(task, task_idx)
        self.logger.info("Starting task: %s", task['task_name'])
        return {
            'current_agent': 'developer',
            'current_task': formatted,
            'current_task_name': task['task_name'],
            'current_task_index': task_idx,
            'revision_count': 0,
            'review_feedback': '',
            'test_results': '',
            'messages': [],
            'communication_log': self.communication(f"Task '{task['task_name']}' ###"),
        }

    def _route_execution(self, state: ProjectState) -> str:
        return state.current_agent or 'officer'
