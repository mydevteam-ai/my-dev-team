from typing import override
from devteam.utils import workspace
from .schemas import DeveloperResponse, SubmitCode
from .base_agent import BaseAgent

class SeniorDeveloper(BaseAgent[DeveloperResponse]):
    output_schema = DeveloperResponse
    tools = [SubmitCode]

    @override
    def _build_inputs(self, state: dict) -> dict:
        inputs = super()._build_inputs(state)
        if workspace_files := state.get('workspace_files', {}):
            workspace_str = workspace.workspace_str_from_files(workspace_files)
        else:
            workspace_str = "No files exist yet. This is the first task. Please create the initial file structure."
        inputs['workspace'] = workspace_str
        return inputs

    @override
    def _update_state(self, parsed_data: DeveloperResponse, current_state: dict) -> dict:
        workspace_files = current_state.get('workspace_files', {}).copy()
        for file_obj in parsed_data.workspace_files:
            workspace_files[file_obj.path] = file_obj.content
        files_modified = len(parsed_data.workspace_files)
        current_revision = current_state.get('revision_count', 0)
        return {
            'workspace_files': workspace_files,
            'review_feedback': '',
            'test_results': '',
            'communication_log': self.communication(f"Wrote/modified {files_modified} file(s)." +  (f" (Revision: {current_revision})" if current_revision > 0 else ""))
        }
