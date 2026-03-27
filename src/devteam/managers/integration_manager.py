from logging import Logger
from langgraph.graph import END
from devteam.state import ProjectState
from devteam.utils import status

class IntegrationManager:
    """Mixin for managing integration tasks."""

    logger: Logger

    def _integration_node(self, state: ProjectState) -> dict:
        return {}

    def _route_integration(self, state: ProjectState) -> str:
        if state.final_report:
            return END
        if not state.test_results:
            return 'final_qa'
        if status.is_approved(state.test_results):
            self.logger.debug("Integration tests passed. Proceeding to reporter.")
            return 'reporter'
        self.logger.error("Integration bugs found! Halting release.")
        return END
