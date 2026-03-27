from langchain_core.messages import RemoveMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from devteam.state import ProjectState
from devteam.utils import CommunicationLog, WithLogging
from .planning_manager import PlanningManager
from .execution_manager import ExecutionManager
from .integration_manager import IntegrationManager

class ProjectManager(CommunicationLog, WithLogging, PlanningManager, ExecutionManager, IntegrationManager):
    max_revision_count: int = 3

    def __init__(self, agents: dict):
        self.agents = agents

    def build_graph(self, memory: BaseCheckpointSaver = None, interrupt_before: list[str] = None) -> CompiledStateGraph:
        workflow = StateGraph(ProjectState)
        workflow.add_node('human', self.dummy_human_node)
        workflow.add_node('manager', self.manager_node)
        workflow.add_node('officer', self.officer_node)
        for node_name, agent in self.agents.items():
            workflow.add_node(node_name, agent.process)
            workflow.add_edge(node_name, 'manager')
        workflow.add_edge('human', 'manager')
        workflow.add_edge(START, 'manager')
        workflow.add_conditional_edges('manager', self.central_router)
        workflow.add_conditional_edges('officer', self.central_router)
        return workflow.compile(checkpointer=memory, interrupt_before=interrupt_before or ['human'])

    def manager_node(self, state: dict) -> dict:
        self.logger.debug("Project Manager is reviewing the project state...")
        match state.get('current_phase', 'planning'):
            case 'planning':
                return self.planning_node(state)
            case 'development':
                return self.execution_node(state)
            case 'integration':
                return self.integration_node(state)
        return {} # Sentinel - in theory should never happen

    def central_router(self, state: dict) -> str:
        if state.get('abort_requested'):
            return END
        match state.get('current_phase', 'planning'):
            case 'planning':
                return self.route_planning(state)
            case 'development':
                return self.route_execution(state)
            case 'integration':
                return self.route_integration(state)
        return END # Sentinel - in theory should never happen

    def dummy_human_node(self, state: dict) -> dict:
        self.logger.debug("Human input received. Resuming workflow...")
        return {'clarification_question': ''}

    def _cleanup_messages(self, messages: list) -> list:
        return [RemoveMessage(id=m.id) for m in messages if m.id]
