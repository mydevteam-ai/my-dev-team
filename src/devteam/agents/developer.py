from typing import override
from devteam.state import ProjectState
from devteam.utils import workspace
from .schemas import DeveloperResponse
from .base_agent import BaseAgent

class SeniorDeveloper(BaseAgent[DeveloperResponse]):
    output_schema = DeveloperResponse

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        inputs['workspace'] = workspace.list_workspace_files(state.workspace_path)
        return inputs

    @override
    def _update_state(self, parsed_data: DeveloperResponse, current_state: ProjectState) -> dict:
        changed_files: dict[str, str] = {f.path: f.content for f in parsed_data.workspace_files}
        files_modified = len(parsed_data.workspace_files)
        current_revision = current_state.task_context.revision_count
        return {
            'task_context': current_state.task_context.model_copy(update={
                'review_feedback': '',
                'test_results': '',
                'changed_files': changed_files,
            }),
            'communication_log': self.communication(f"Wrote/modified {files_modified} file(s)." + (f" (Revision: {current_revision})" if current_revision > 0 else ""))
        }
