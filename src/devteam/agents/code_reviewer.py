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
        changed = state.task_context.changed_files
        all_paths = workspace.live_paths(state.workspace_path)
        if not all_paths and not changed:
            inputs['workspace'] = "No files exist in the workspace."
            return inputs
        sections: list[str] = []
        if changed:
            sections.append("## Files changed in this revision (full content)\n\n"
                            + workspace.workspace_str_from_files(changed).strip())
        other_paths = sorted(p for p in all_paths if p not in changed)
        if other_paths:
            listing = '\n'.join(f"- {p}" for p in other_paths)
            sections.append(
                f"## Other workspace files ({len(other_paths)}) - paths only\n\n"
                f"Use the `ReadFile` tool to fetch the content of any file below that you need "
                f"to verify imports, integration points or context.\n\n{listing}"
            )
        inputs['workspace'] = '\n\n'.join(sections).strip() or "No files exist in the workspace."
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
            'task_context': current_state.task_context.model_copy(update={'review_feedback': feedback}),
            'communication_log': self.communication(f"{status_str}\n{feedback}")
        }
