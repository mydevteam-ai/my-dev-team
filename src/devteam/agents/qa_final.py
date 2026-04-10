from typing import override
from devteam.state import ProjectState
from devteam.utils import status, workspace
from .schemas import FinalQAResponse
from .base_agent import BaseAgent

class FinalQAEngineer(BaseAgent[FinalQAResponse]):
    output_schema = FinalQAResponse

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        if workspace_files := workspace.read_all_files(state.workspace_path):
            workspace_str = workspace.workspace_str_from_files(workspace_files)
        else:
            workspace_str = "No files exist in the workspace."
        inputs['workspace'] = workspace_str.strip()
        return inputs

    @override
    def _map_tool_to_output(self, tool_name: str, tool_args: dict) -> FinalQAResponse:
        if tool_name == 'ApproveCode':
            return FinalQAResponse(test_results='PASSED')
        if tool_name == 'ReportIssues':
            return FinalQAResponse(test_results=tool_args['feedback'])
        raise ValueError(f"Unexpected tool call: {tool_name}")

    @override
    def _update_state(self, parsed_data: FinalQAResponse, current_state: ProjectState) -> dict:
        results = parsed_data.test_results
        if status.is_approved(results):
            results = 'APPROVED'
        status_str = 'APPROVED' if results == 'APPROVED' else 'INTEGRATION BUGS FOUND'
        tc_update: dict = {'test_results': results}
        if not status.is_approved(results):
            tc_update['current_task'] = "FINAL INTEGRATION: Fix the overarching bugs identified in the Final QA test results."
            tc_update['revision_count'] = 0
        return {
            'task_context': current_state.task_context.model_copy(update=tc_update),
            'communication_log': self.communication(f"{status_str}\n{results}")
        }
