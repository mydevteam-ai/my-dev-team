from typing import override
from devteam.state import ProjectState
from devteam.utils import status, workspace
from .schemas import CodeReviewerResponse
from .base_agent import BaseAgent

class CodeReviewer(BaseAgent[CodeReviewerResponse]):
    output_schema = CodeReviewerResponse

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        workspace_str = ''
        if state.workspace_files:
            workspace_str = workspace.workspace_str_from_files(state.workspace_files)
        else:
            workspace_str = "No files exist in the workspace."
        inputs['workspace'] = workspace_str.strip()
        return inputs

    @override
    def _map_tool_to_output(self, tool_name: str, tool_args: dict) -> CodeReviewerResponse:
        if tool_name == 'ApproveCode':
            return CodeReviewerResponse(review_feedback='APPROVED')
        if tool_name == 'ReportIssues':
            return CodeReviewerResponse(review_feedback=tool_args['feedback'])
        raise ValueError(f"Unexpected tool call: {tool_name}")

    @override
    def _update_state(self, parsed_data: CodeReviewerResponse, current_state: ProjectState) -> dict:
        feedback = parsed_data.review_feedback
        if status.is_approved(feedback):
            feedback = 'APPROVED'
        status_str = 'APPROVED' if feedback == 'APPROVED' else 'REQUESTED CHANGES'
        return {
            'review_feedback': feedback,
            'communication_log': self.communication(f"{status_str}\n{feedback}")
        }
