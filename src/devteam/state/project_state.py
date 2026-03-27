import operator
from typing import Any, TypedDict, Annotated, NotRequired, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

type ProjectPhase = Literal['planning', 'development', 'integration', 'complete']

class ProjectState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    current_phase: ProjectPhase
    current_agent: str
    requirements: str
    specs: str
    human_answer: str
    clarification_question: str
    runtime: str
    pending_tasks: list[dict[str, Any]]
    workspace_files: dict[str, str]
    current_task_index: int
    current_task: str
    review_feedback: str
    test_results: str
    revision_count: int
    final_report: str
    integration_bugs: list[str]
    communication_log: Annotated[list[str], operator.add]
    workspace_path: str
    abort_requested: NotRequired[bool]
    error: NotRequired[bool]
    error_message: NotRequired[str]
