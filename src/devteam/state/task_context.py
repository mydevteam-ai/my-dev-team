from pydantic import BaseModel, Field

class TaskContext(BaseModel):
    """Isolated state for a single task execution cycle (dev -> review -> qa)."""
    current_agent: str = ''
    current_task: str = ''
    current_task_name: str = ''
    current_task_index: int = 0
    review_feedback: str = ''
    test_results: str = ''
    raw_test_results: str = ''
    revision_count: int = 0
    changed_files: dict[str, str] = Field(default_factory=dict)
