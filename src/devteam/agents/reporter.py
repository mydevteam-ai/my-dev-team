from typing import override
from devteam.state import ProjectState
from devteam.utils import sanitizer
from .schemas import ReporterResponse
from .base_agent import BaseAgent

class Reporter(BaseAgent[ReporterResponse]):
    output_schema = ReporterResponse

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        inputs['history'] = sanitizer.sanitize_for_prompt('\n\n'.join(state.communication_log), ['history'])
        return inputs
