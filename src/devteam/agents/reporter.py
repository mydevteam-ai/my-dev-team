from devteam.utils import sanitizer, workspace
from .schemas import ReporterResponse, SubmitReport
from .base_agent import BaseAgent

class Reporter(BaseAgent[ReporterResponse]):
    output_schema = ReporterResponse
    tools = [SubmitReport]

    def _build_inputs(self, state: dict) -> dict:
        inputs = super()._build_inputs(state)
        if workspace_files := state.get('workspace_files', {}):
            workspace_str = workspace.workspace_str_from_files(workspace_files)
        else:
            workspace_str = "No files were generated."
        inputs['workspace'] = workspace_str
        communication_log = state.get('communication_log', [])
        history_str = '\n\n'.join(communication_log)
        inputs['history'] = sanitizer.sanitize_for_prompt(history_str, ['history'])
        return inputs
