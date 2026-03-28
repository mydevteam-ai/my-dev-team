from pydantic import BaseModel, Field, ConfigDict, computed_field

class FinalResult(BaseModel):
    model_config = ConfigDict(extra='ignore')

    thread_id: str = ''
    requirements: str = ''
    final_report: str | None = None
    workspace_files: dict[str, str] = Field(default_factory=dict)
    integration_bugs: list[str] = Field(default_factory=list)
    failed_tasks: list[str] = Field(default_factory=list)
    abort_requested: bool = False
    error: bool = False
    error_message: str | None = None

    @computed_field
    def success(self) -> bool:
        return not self.abort_requested and len(self.integration_bugs) == 0

    @computed_field
    def has_bugs(self) -> bool:
        return len(self.integration_bugs) > 0
