from devteam.state import ProjectState
from .schemas import MigrationAnalysisResponse
from .base_agent import BaseAgent

class CodeAnalyzer(BaseAgent[MigrationAnalysisResponse]):
    output_schema = MigrationAnalysisResponse

    def _update_state(self, parsed_data: MigrationAnalysisResponse, current_state: ProjectState) -> dict:
        tasks = [t.model_dump() for t in parsed_data.pending_tasks]
        return {
            'specs': parsed_data.specs,
            'runtime': parsed_data.runtime,
            'pending_tasks': tasks,
            'communication_log': self.communication(
                f"Analysis complete. Runtime: {parsed_data.runtime}. Tasks identified: {len(tasks)}."
            ),
        }
