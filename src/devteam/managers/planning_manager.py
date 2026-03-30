from logging import Logger
from langgraph.graph import END
from devteam import settings
from devteam.state import ProjectState

class PlanningManager:
    """Mixin for managing planning phase."""

    logger: Logger

    def _planning_node(self, state: ProjectState) -> dict:
        if len(state.pending_tasks) > 0 and not state.tasks_approved: # Architect has finished
            if settings.ask_approval:
                return {} # Wait for user to approve the task plan
            return {
                'current_phase': 'development',
                'tasks_approved': True,
                'messages': self._cleanup_messages(state.messages)
            }
        if state.specs and not state.specs_approved: # PM has finished
            if settings.ask_approval:
                return {} # Wait for user to approve the specifications
            return {
                'specs_approved': True,
                'messages': self._cleanup_messages(state.messages)
            }
        return {} # Sentinel - in theory should never happen

    def _route_planning(self, state: ProjectState) -> str:
        if state.clarification_question:
            return 'human'
        if not state.specs:
            return 'pm' # TODO: how to prevent cycle if PM didn't return specs?
        if not state.specs_approved:
            return 'human' # Pause for spec approval
        if not state.pending_tasks:
            return 'architect' # TODO: how to prevent cycle if architect didn't return tasks?
        if not state.tasks_approved:
            return 'human' # Pause for task plan approval
        return END # Sentinel - in theory should never happen
