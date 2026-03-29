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

def _merge_workspace_files(existing: dict[str, str], update: dict[str, str]) -> dict[str, str]:
    """Merge workspace file dicts so parallel task branches can write independently."""
    return {**existing, **update}

def _last_value[T](existing: T, update: T) -> T:
    """Reducer that accepts concurrent writes from parallel branches (last write wins)."""
    return update

class ProjectState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    current_phase: Annotated[ProjectPhase, _last_value] = 'planning'
    current_agent: Annotated[str, _last_value] = ''
    requirements: str = ''
    specs: str = ''
    human_answer: str = ''
    clarification_question: str = ''
    runtime: str = ''
    pending_tasks: list[PendingTask] = Field(default_factory=list)
    workspace_files: Annotated[dict[str, str], _merge_workspace_files] = Field(default_factory=dict)
    current_task: Annotated[str, _last_value] = ''
    current_task_name: Annotated[str, _last_value] = ''
    review_feedback: Annotated[str, _last_value] = ''
    test_results: Annotated[str, _last_value] = ''
    revision_count: Annotated[int, _last_value] = 0
    final_report: Annotated[str, _last_value] = ''
    integration_bugs: list[str] = Field(default_factory=list)
    communication_log: Annotated[list[str], operator.add] = Field(default_factory=list)
    failed_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    completed_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    in_progress_tasks: Annotated[list[str], operator.add] = Field(default_factory=list)
    pending_dispatch: Annotated[list[str], _last_value] = Field(default_factory=list)
    raw_test_results: Annotated[str, _last_value] = ''
    workspace_path: str = ''
    abort_requested: Annotated[bool, _last_value] = False
    error: Annotated[bool, _last_value] = False
    error_message: Annotated[str, _last_value] = ''
