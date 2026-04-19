from functools import cached_property
from logging import Logger
from typing import Callable
from langchain_core.messages import HumanMessage
from devteam.state import ProjectState, PendingTask, TaskContext
from devteam.utils import status, tasks

class ExecutionManager:
    """Mixin for managing development tasks."""

    logger: Logger
    max_revision_count: int
    communication: Callable
    agents: dict

    @cached_property
    def _developer_node(self) -> str:
        """First developer node name: fan-out start or single developer."""
        return 'developer_a' if ('developer_a' in self.agents and 'developer_b' in self.agents) else 'developer'

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
        task_context = state.task_context
        current_revision = task_context.revision_count
        revision_agent = task_context.winner_developer or 'developer'

        def _next(agent: str) -> dict:
            return {'task_context': task_context.model_copy(update={'current_agent': agent})}

        def _revise(feedback_label: str, feedback: str) -> dict:
            instruction = (
                f"The {feedback_label} rejected your implementation. "
                "Please read the feedback below, fix the code and use your tools to update the workspace.\n\n"
                f"### {feedback_label} Feedback ###\n{feedback}"
            )
            return {
                'task_context': task_context.model_copy(update={
                    'current_agent': revision_agent,
                    'revision_count': current_revision + 1,
                    'review_feedback': '',
                    'test_results': '',
                }),
                'messages': [HumanMessage(content=instruction)],
                'communication_log': self.communication(f"Revision {current_revision + 1} requested by {feedback_label}.")
            }

        match task_context.current_agent:
            case 'developer_a':
                return _next('reviewer' if task_context.winner_developer else 'developer_b')
            case 'developer_b':
                return _next('judge')
            case 'judge' | 'developer':
                return _next('reviewer')
            case _ if not task_context.review_feedback:
                return _next('reviewer')

        if not status.is_approved(task_context.review_feedback):
            if current_revision < self.max_revision_count:
                return _revise('Code Reviewer', task_context.review_feedback)
            self.logger.warning("Max revisions reached with a rejected review. Running QA on best attempt.")
            return _next('qa')

        if not task_context.test_results:
            return _next('qa')

        if not status.is_approved(task_context.test_results) and current_revision < self.max_revision_count:
            return _revise('QA', task_context.test_results)

        return {
            'task_context': task_context.model_copy(update={'current_agent': 'officer'}),
            'completed_tasks': [task_context.current_task_name],
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
                'task_context': TaskContext(),
                'messages': self._cleanup_messages(state.messages),
            }

        task_idx = next(
            (i + 1 for i, t in enumerate(state.pending_tasks) if t['task_name'] == task['task_name']), 1
        )
        formatted = tasks.task_to_markdown(task, task_idx)
        initial_agent = self._developer_node
        self.logger.info("Starting task: %s", task['task_name'])
        return {
            'task_context': TaskContext(
                current_agent=initial_agent,
                current_task=formatted,
                current_task_name=task['task_name'],
                current_task_index=task_idx,
            ),
            'messages': [],
            'communication_log': self.communication(f"Task '{task['task_name']}' ###"),
        }

    def _route_execution(self, state: ProjectState) -> str:
        return state.task_context.current_agent or 'officer'
