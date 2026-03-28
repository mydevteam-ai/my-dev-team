import asyncio
from typing import override
from pathlib import Path
from devteam.state import ProjectState
from devteam.tools import DockerSandbox
from devteam.utils import sanitizer, status, workspace
from .schemas import ApproveCode, QAEngineerResponse, ReportIssues
from .base_agent import BaseAgent

class QAEngineer(BaseAgent[QAEngineerResponse]):
    output_schema = QAEngineerResponse
    tools = [ApproveCode, ReportIssues]
    sandbox: DockerSandbox = None

    @override
    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = super()._build_inputs(state)
        if workspace_files := state.workspace_files:
            workspace_str = workspace.workspace_str_from_files(workspace_files)
            if state.raw_test_results:
                inputs['test_results'] = sanitizer.sanitize_for_prompt(state.raw_test_results, ['test_results'])
        else:
            workspace_str = "No files exist in the workspace."
        inputs['workspace'] = workspace_str.strip()
        return inputs

    def _run_tests(self, state: ProjectState) -> str:
        target_runtime = state.runtime or 'auto'
        workspace_path = Path(state.workspace_path)
        self.logger.info("Running tests in Docker Sandbox...")
        test_results = self.sandbox.run_tests(workspace_path, runtime=target_runtime)
        self.logger.debug("Sandbox Output:\n%s", test_results)
        return test_results

    @override
    def _map_tool_to_output(self, tool_name: str, tool_args: dict) -> QAEngineerResponse:
        if tool_name == 'ApproveCode':
            return QAEngineerResponse(test_results='PASSED')
        if tool_name == 'ReportIssues':
            return QAEngineerResponse(test_results=tool_args['feedback'])
        raise ValueError(f"Unexpected tool call: {tool_name}")

    @override
    def _update_state(self, parsed_data: QAEngineerResponse, current_state: ProjectState) -> dict:
        results = parsed_data.test_results
        if status.is_approved(results):
            results = 'APPROVED'
        status_str = 'APPROVED' if results == 'APPROVED' else 'BUGS FOUND'
        return {
            'test_results': results,
            'communication_log': self.communication(f"{status_str}\n{results}")
        }

    async def _pre_process(self, state: ProjectState) -> ProjectState:
        if self.sandbox and state.workspace_files:
            state.raw_test_results = await asyncio.to_thread(self._run_tests, state)
        return state

    def with_sandbox(self, sandbox: DockerSandbox):
        self.sandbox = sandbox
        return self
