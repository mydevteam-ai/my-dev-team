from typing import override
from devteam.state import ProjectState
from devteam.utils import workspace
from .schemas import DeveloperResponse, SubmitCode
from .base_agent import BaseAgent

class SeniorDeveloper(BaseAgent[DeveloperResponse]):
    output_schema = DeveloperResponse
    tools = [SubmitCode]

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        if state.workspace_files:
            workspace_str = workspace.workspace_str_from_files(state.workspace_files)
        else:
            workspace_str = "No files exist yet. This is the first task. Please create the initial file structure."
        inputs['workspace'] = workspace_str
        return inputs

    @override
    def _update_state(self, parsed_data: DeveloperResponse, current_state: ProjectState) -> dict:
        workspace_files = current_state.workspace_files.copy()
        for file_obj in parsed_data.workspace_files:
            workspace_files[file_obj.path] = file_obj.content
        files_modified = len(parsed_data.workspace_files)
        current_revision = current_state.revision_count
        return {
            'workspace_files': workspace_files,
            'review_feedback': '',
            'test_results': '',
            'communication_log': self.communication(f"Wrote/modified {files_modified} file(s)." +  (f" (Revision: {current_revision})" if current_revision > 0 else ""))
        }
