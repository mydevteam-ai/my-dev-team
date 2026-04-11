from langgraph.graph import END
from devteam.state import ProjectState
from devteam import settings
from .base_manager import BaseManager

class MigrationManager(BaseManager):
    """Orchestrates the migration workflow: analysis -> translation -> validation."""

    def _planning_node(self, state: ProjectState) -> dict:
        """Transition to translation phase once CodeAnalyzer has output specs + tasks."""
        if state.specs and state.pending_tasks:
            if settings.ask_approval:
                return {}  # Wait for user to approve before proceeding
            return {
                'current_phase': 'development',
                'specs_approved': True,
                'tasks_approved': True,
                'messages': self._cleanup_messages(state.messages),
            }
        return {}

    def _route_planning(self, state: ProjectState) -> str:
        if state.clarification_question:
            return 'human'
        if not state.specs:
            return 'analyzer'
        if not state.tasks_approved:
            if settings.ask_approval:
                return 'human'
            return 'manager'
        return END
