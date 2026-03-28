import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

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
    current_agent: str = ''
    requirements: str = ''
    specs: str = ''
    human_answer: str = ''
    clarification_question: str = ''
    runtime: str = ''
    pending_tasks: list[PendingTask] = Field(default_factory=list)
    workspace_files: dict[str, str] = Field(default_factory=dict)
    current_task_index: int = 0
    current_task: str = ''
    review_feedback: str = ''
    test_results: str = ''
    revision_count: int = 0
    final_report: str = ''
    integration_bugs: list[str] = Field(default_factory=list)
    communication_log: Annotated[list[str], operator.add] = Field(default_factory=list)
    failed_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    raw_test_results: str = ''
    workspace_path: str = ''
    abort_requested: bool = False
    error: bool = False
    error_message: str = ''
