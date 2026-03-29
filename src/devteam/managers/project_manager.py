from langchain_core.messages import RemoveMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from devteam import settings
from devteam.state import ProjectState
from devteam.utils import CommunicationLog, WithLogging
from .planning_manager import PlanningManager
from .execution_manager import ExecutionManager
from .integration_manager import IntegrationManager

class ProjectManager(CommunicationLog, WithLogging, PlanningManager, ExecutionManager, IntegrationManager):
    max_revision_count: int = 3

    def __init__(self, agents: dict):
        self.agents = agents
        if settings.no_parallel:
            self._find_ready_tasks = self._find_first_ready_task

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

    def _handle_agent_error(self, state: ProjectState) -> dict:
        if state.current_phase == 'development':
            task_name = state.current_task_name or "Unknown task"
            task_label = f"{task_name}: {state.current_task[:60].strip()}"
            self.logger.warning("Agent error on '%s'. Skipping to next task.", task_label)
            return {
                'error': False,
                'error_message': '',
                'current_agent': 'officer',
                'completed_tasks': [state.current_task_name] if state.current_task_name else [],
                'failed_tasks': [task_label],
            }
        self.logger.error("Agent error in '%s' phase. Halting workflow.", state.current_phase)
        return {'abort_requested': True}

    def _manager_node(self, state: ProjectState) -> dict:
        if state.error:
            return self._handle_agent_error(state)
        self.logger.debug("Project Manager is reviewing the project state...")
        match state.current_phase:
            case 'planning':
                return self._planning_node(state)
            case 'development':
                return self._execution_node(state)
            case 'integration':
                return self._integration_node(state)
        return {} # Sentinel - in theory should never happen

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
        return END # Sentinel - in theory should never happen

    def _dummy_human_node(self, state: ProjectState) -> dict:
        self.logger.debug("Human input received. Resuming workflow...")
        return {'clarification_question': ''}

    def _cleanup_messages(self, messages: list) -> list:
        return [RemoveMessage(id=m.id) for m in messages if m.id]
