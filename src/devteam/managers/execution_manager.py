from logging import Logger
from typing import Callable
from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Send
from devteam import settings
from devteam.state import ProjectState, PendingTask
from devteam.utils import status, tasks

class ExecutionManager:
    """Mixin for managing development tasks."""

    logger: Logger
    max_revision_count: int
    communication: Callable

    def _find_ready_tasks(self, state: ProjectState) -> list[PendingTask]:
        """Return all tasks whose dependencies are all complete and haven't been dispatched yet."""
        completed = set(state.completed_tasks)
        in_progress = set(state.in_progress_tasks)
        already_handled = completed | in_progress
        return [
            task for task in state.pending_tasks
            if task['task_name'] not in already_handled
            and all(dep in completed for dep in task.get('dependencies', []))
        ]

    def _find_first_ready_task(self, state: ProjectState) -> PendingTask | None:
        """Return the first task whose dependencies are met and hasn't been dispatched yet (sequential mode)."""
        completed = set(state.completed_tasks)
        already_handled = completed | set(state.in_progress_tasks)
        return next(
            (task for task in state.pending_tasks
             if task['task_name'] not in already_handled
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
        """Find ready tasks and set up for fan-out, or transition to integration."""
        self.logger.debug(
            "Officer state — completed: %s | in_progress: %s | pending: %s",
            state.completed_tasks,
            state.in_progress_tasks,
            [t['task_name'] for t in state.pending_tasks],
        )
        raw = self._find_ready_tasks(state)
        ready: list[PendingTask] = [raw] if isinstance(raw, dict) else (raw or [])

        if not ready:
            all_names = {t['task_name'] for t in state.pending_tasks}
            if all_names <= set(state.completed_tasks):
                self.logger.debug("All tasks complete. Routing to integration.")
                return {
                    'current_phase': 'integration',
                    'current_agent': '',
                    'current_task': '',
                    'current_task_name': '',
                    'pending_dispatch': [],
                    'test_results': '',
                    'messages': self._cleanup_messages(state.messages),
                }
            if settings.no_parallel:
                # Sequential mode: no parallel branches exist, so "waiting" means something went
                # wrong with task name tracking. Treat all in-progress tasks as complete and
                # proceed to integration rather than terminating the workflow.
                self.logger.warning(
                    "Officer: no ready tasks in sequential mode (%s complete, %s in-progress). "
                    "Proceeding to integration.",
                    set(state.completed_tasks), set(state.in_progress_tasks),
                )
                return {
                    'current_phase': 'integration',
                    'current_agent': '',
                    'current_task': '',
                    'current_task_name': '',
                    'pending_dispatch': [],
                    'test_results': '',
                    'messages': self._cleanup_messages(state.messages),
                }
            # Other parallel branches are still processing - this branch is finished
            self.logger.debug(
                "Officer: no ready tasks yet (%d/%d complete). Waiting for in-progress work.",
                len(set(state.completed_tasks)), len(state.pending_tasks),
            )
            return {'current_agent': 'officer:done', 'pending_dispatch': []}

        task_names = [t['task_name'] for t in ready]
        self.logger.info("Fanning out %d task(s): %s", len(ready), ', '.join(task_names))
        return {
            'current_agent': 'fanout',
            'in_progress_tasks': task_names,
            'pending_dispatch': task_names,
            'communication_log': self.communication(
                f"Dispatching {len(ready)} task(s) in parallel: {', '.join(task_names)}"
            ),
        }

    def _route_execution(self, state: ProjectState) -> str | list:
        agent = state.current_agent

        if agent == 'fanout':
            task_map = {t['task_name']: t for t in state.pending_tasks}
            sends = []
            for name in state.pending_dispatch:
                task = task_map[name]
                task_idx = next(
                    (i + 1 for i, t in enumerate(state.pending_tasks) if t['task_name'] == name), 1
                )
                formatted = tasks.task_to_markdown(task, task_idx)
                sends.append(Send('developer', {
                    # Shared read-only context the branch needs
                    'requirements': state.requirements,
                    'specs': state.specs,
                    'runtime': state.runtime,
                    'workspace_files': dict(state.workspace_files),
                    'workspace_path': state.workspace_path,
                    'pending_tasks': list(state.pending_tasks),
                    'completed_tasks': list(state.completed_tasks),
                    'in_progress_tasks': list(state.in_progress_tasks),
                    'current_phase': 'development',
                    # Task-specific state
                    'current_agent': 'developer',
                    'current_task': formatted,
                    'current_task_name': name,
                    'revision_count': 0,
                    'review_feedback': '',
                    'test_results': '',
                    'messages': [],
                    'communication_log': self.communication(f"Task '{name}' ###"),
                }))
            return sends

        if agent == 'officer:done':
            return END

        return agent or 'officer'
