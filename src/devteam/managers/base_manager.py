from abc import abstractmethod
from langchain_core.messages import RemoveMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from devteam.state import ProjectState
from devteam.utils import CommunicationLog, WithLogging
from devteam import settings
from .execution_manager import ExecutionManager
from .integration_manager import IntegrationManager

class BaseManager(CommunicationLog, WithLogging, ExecutionManager, IntegrationManager):
    """Base class for all workflow managers. Provides the graph structure,
    error handling and phase dispatch skeleton. Subclasses implement the
    planning-phase node and router for their specific workflow."""

    max_revision_count: int = settings.max_revision_count

    def __init__(self, agents: dict):
        self.agents = agents

    def build_graph(self, memory: BaseCheckpointSaver = None, interrupt_before: list[str] = None) -> CompiledStateGraph:
        workflow = StateGraph(ProjectState)
        workflow.add_node('human', self._dummy_human_node)
        workflow.add_node('manager', self._manager_node)
        workflow.add_node('officer', self._officer_node)
        for node_name, agent in self.agents.items():
            workflow.add_node(node_name, agent.process)
            workflow.add_edge(node_name, 'manager')
        workflow.add_edge('human', 'manager')
        workflow.add_edge(START, 'manager')
        workflow.add_conditional_edges('manager', self._central_router)
        workflow.add_conditional_edges('officer', self._central_router)
        return workflow.compile(checkpointer=memory, interrupt_before=interrupt_before or ['human'])

    def _manager_node(self, state: ProjectState) -> dict:
        if state.error:
            return self._handle_agent_error(state)
        self.logger.debug("%s is reviewing the project state...", type(self).__name__)
        match state.current_phase:
            case 'planning':
                return self._planning_node(state)
            case 'development':
                return self._execution_node(state)
            case 'integration':
                return self._integration_node(state)
        return {}

    def _central_router(self, state: ProjectState) -> str:
        if state.abort_requested:
            return END
        match state.current_phase:
            case 'planning':
                return self._route_planning(state)
            case 'development':
                return self._route_execution(state)
            case 'integration':
                return self._route_integration(state)
        return END

    def _handle_agent_error(self, state: ProjectState) -> dict:
        if state.current_phase == 'development':
            task_context = state.task_context
            task_name = task_context.current_task_name or f"Task {task_context.current_task_index}"
            task_label = f"{task_name}: {task_context.current_task[:60].strip()}"
            self.logger.warning("Agent error on '%s'. Skipping to next task.", task_label)
            return {
                'error': False,
                'error_message': '',
                'task_context': task_context.model_copy(update={'current_agent': 'officer'}),
                'completed_tasks': [task_context.current_task_name] if task_context.current_task_name else [],
                'failed_tasks': [task_label],
            }
        self.logger.error("Agent error in '%s' phase. Halting workflow.", state.current_phase)
        return {'abort_requested': True}

    def _dummy_human_node(self, state: ProjectState) -> dict:
        self.logger.debug("Human input received. Resuming workflow...")
        return {'clarification_question': ''}

    def _cleanup_messages(self, messages: list) -> list:
        return [RemoveMessage(id=m.id) for m in messages if m.id]

    @abstractmethod
    def _planning_node(self, state: ProjectState) -> dict:
        """Handle the planning phase manager node."""

    @abstractmethod
    def _route_planning(self, state: ProjectState) -> str:
        """Route within the planning phase."""
