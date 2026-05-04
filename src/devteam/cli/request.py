from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

class _BaseRunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    provider: str
    rpm: int = 0
    workflow: str = 'development'
    fanout: bool = False

class StartRequest(_BaseRunRequest):
    kind: Literal['start'] = 'start'
    project_file_path: str
    seed_path: str | None = None

class ResumeRequest(_BaseRunRequest):
    kind: Literal['resume'] = 'resume'
    resume_thread: str
    feedback: str | None = None
    feedback_source: str = 'reviewer'
    checkpoint_id: str | None = None

RunRequest = Annotated[Union[StartRequest, ResumeRequest], Field(discriminator='kind')]
