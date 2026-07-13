from typing import override
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from devteam.state import ProjectState
from devteam.utils import workspace
from devteam.utils.edits import EditError, apply_edits
from .schemas import DeveloperResponse, WorkspaceFile
from .base_agent import BaseAgent

class SeniorDeveloper(BaseAgent[DeveloperResponse]):
    output_schema = DeveloperResponse

    @override
    def _input_workspace(self, state: ProjectState) -> str:
        return workspace.list_workspace_files(state.workspace_path)

    @override
    def _map_tool_to_output(self, tool_name: str, tool_args: dict, state: ProjectState = None) -> DeveloperResponse:
        parsed = super()._map_tool_to_output(tool_name, tool_args, state)
        return self._resolve_edits(parsed, state)

    def _resolve_edits(self, parsed: DeveloperResponse, state: ProjectState) -> DeveloperResponse:
        """Resolve edit-form files against the live workspace into full content.

        A failed or ambiguous match raises ValidationError, so the existing
        self-repair loop re-prompts the model with the exact failure. All
        failures across the submission are collected into one re-ask.
        """
        workspace_path = getattr(state, 'workspace_path', '') or ''
        resolved: list[WorkspaceFile] = []
        failures: list[InitErrorDetails] = []
        for i, wf in enumerate(parsed.workspace_files):
            if not wf.edits:
                resolved.append(wf)
                continue
            text = workspace.read_live_file(wf.path, workspace_path)
            if text is None:
                failures.append(self._edit_failure(
                    ('workspace_files', i, 'path'), wf.path,
                    f"File does not exist: {wf.path}. Submit the file's full `content` to create a new file.",
                ))
                continue
            try:
                new_text = apply_edits(text, wf.path, [(e.old_text, e.new_text) for e in wf.edits])
            except EditError as exc:
                failures.append(self._edit_failure(
                    ('workspace_files', i, 'edits', exc.index, 'old_text'),
                    wf.edits[exc.index].old_text, str(exc),
                ))
                continue
            resolved.append(wf.model_copy(update={'content': new_text, 'edits': None}))
        if failures:
            raise ValidationError.from_exception_data('SubmitCode', failures)
        return parsed.model_copy(update={'workspace_files': resolved})

    @staticmethod
    def _edit_failure(loc: tuple, value, message: str) -> InitErrorDetails:
        return InitErrorDetails(
            type=PydanticCustomError('edit_failed', '{reason}', {'reason': message}),
            loc=loc,
            input=value,
        )

    @override
    def _update_state(self, parsed_data: DeveloperResponse, current_state: ProjectState) -> dict:
        files: dict[str, str] = {f.path: f.content for f in parsed_data.workspace_files}
        files_modified = len(parsed_data.workspace_files)
        current_revision = current_state.task_context.revision_count
        new_drafts = {**current_state.task_context.developer_drafts, self.node_name: files}
        return {
            'task_context': current_state.task_context.model_copy(update={
                'review_feedback': '',
                'test_results': '',
                'developer_drafts': new_drafts,
            }),
            'communication_log': self.communication(f"Wrote/modified {files_modified} file(s)." + (f" (Revision: {current_revision})" if current_revision > 0 else ""))
        }
