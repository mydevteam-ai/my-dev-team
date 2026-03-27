from logging import Logger
from langgraph.graph import END
from devteam.state import ProjectState

class PlanningManager:
    """Mixin for managing planning phase."""

    logger: Logger

    def _planning_node(self, state: ProjectState) -> dict:
        if len(state.pending_tasks) > 0: # Architect has finished, let's proceed to development
            return {
                'current_phase': 'development',
                'messages': self._cleanup_messages(state.messages)
            }
        if state.specs: # PM has finished - clean up messages
            return {
                'messages': self._cleanup_messages(state.messages)
            }
        return {} # Sentinel - in theory should never happen

    def _route_planning(self, state: ProjectState) -> str:
        if state.clarification_question:
            return 'human'
        if not state.specs:
            return 'pm' # TODO: how to prevent cycle if PM didn't return specs?
        if not state.pending_tasks:
            return 'architect' # TODO: how to prevent cycle if architect didn't return tasks?
        return END # Sentinel - in theory should never happen
