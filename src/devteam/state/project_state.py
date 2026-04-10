import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from .task_context import TaskContext

type ProjectPhase = Literal['planning', 'development', 'integration', 'complete']

class PendingTask(TypedDict):
    task_name: str
    user_story: str
    acceptance_criteria: list[str]
    dependencies: list[str]

class ProjectState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    current_phase: ProjectPhase = 'planning'
    requirements: str = ''
    specs: str = ''
    specs_approved: bool = False
    tasks_approved: bool = False
    human_answer: str = ''
    clarification_question: str = ''
    runtime: str = ''
    pending_tasks: list[PendingTask] = Field(default_factory=list)
    task_context: TaskContext = Field(default_factory=TaskContext)
    final_report: str = ''
    integration_bugs: list[str] = Field(default_factory=list)
    communication_log: Annotated[list[str], operator.add] = Field(default_factory=list)
    failed_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    completed_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    workspace_path: str = ''
    abort_requested: bool = False
    error: bool = False
    error_message: str = ''
