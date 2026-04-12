from langchain_core.messages import HumanMessage
from devteam.state import ProjectState
from devteam.utils import sanitizer
from .schemas import ReporterResponse
from .base_agent import BaseAgent

class Reporter(BaseAgent[ReporterResponse]):
    output_schema = ReporterResponse

    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        history = sanitizer.sanitize_for_prompt('\n\n'.join(state.communication_log), ['history'])
        if history:
            data_msg = inputs['messages'][0]
            inputs['messages'][0] = HumanMessage(content=data_msg.content + f"\n\n<history>\n{history}\n</history>")
        return inputs
