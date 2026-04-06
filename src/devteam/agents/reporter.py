from devteam.state import ProjectState
from devteam.utils import sanitizer, workspace
from .schemas import ReporterResponse
from .base_agent import BaseAgent

class Reporter(BaseAgent[ReporterResponse]):
    output_schema = ReporterResponse

    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        if state.workspace_files:
            workspace_str = workspace.workspace_str_from_files(state.workspace_files)
        else:
            workspace_str = "No files were generated."
        inputs['workspace'] = workspace_str
        inputs['history'] = sanitizer.sanitize_for_prompt('\n\n'.join(state.communication_log), ['history'])
        return inputs
