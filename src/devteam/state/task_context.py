from pydantic import BaseModel, Field

class TaskContext(BaseModel):
    """Isolated state for a single task execution cycle (dev -> review -> qa)."""
    current_agent: str = ''
    current_task: str = ''
    current_task_name: str = ''
    current_task_index: int = 0
    current_task_complexity: str = ''
    review_feedback: str = ''
    test_results: str = ''
    raw_test_results: str = ''
    revision_count: int = 0
    developer_drafts: dict[str, dict[str, str]] = Field(default_factory=dict)
    winner_developer: str = ''

    @property
    def changed_files(self) -> dict[str, str]:
        """Current working files: winner's draft in fan-out mode, or the single developer's draft."""
        if self.winner_developer:
            return self.developer_drafts.get(self.winner_developer, {})
        return next(iter(self.developer_drafts.values()), {})
