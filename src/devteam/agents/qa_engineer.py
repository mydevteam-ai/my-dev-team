from typing import override
from pathlib import Path
from devteam.tools import DockerSandbox
from devteam.utils import status, workspace
from .schemas import ApproveCode, QAEngineerResponse, ReportIssues
from .base_agent import BaseAgent

class QAEngineer(BaseAgent[QAEngineerResponse]):
    output_schema = QAEngineerResponse
    tools = [ApproveCode, ReportIssues]
    sandbox: DockerSandbox = None

    @override
    def _build_inputs(self, state: dict) -> dict:
        inputs = super()._build_inputs(state)
        workspace_str = ''
        if workspace_files := state.get('workspace_files', {}):
            workspace_str = workspace.workspace_str_from_files(workspace_files)
            if state.get('raw_test_results', ''):
                inputs['test_results'] = self.sanitize_for_prompt(state['raw_test_results'], ['test_results'])
        else:
            workspace_str = "No files exist in the workspace."
        inputs['workspace'] = workspace_str.strip()
        return inputs

    def _run_tests(self, state: dict) -> str:
        target_runtime = state.get('runtime', 'auto')
        workspace_path = Path(state['workspace_path'])
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
    def _update_state(self, parsed_data: QAEngineerResponse, current_state: dict) -> dict:
        results = parsed_data.test_results
        if status.is_approved_status(results):
            results = 'APPROVED'
        status_str = 'APPROVED' if results == 'APPROVED' else 'BUGS FOUND'
        return {
            'test_results': results,
            'communication_log': self.communication(f"{status_str}\n{results}")
        }

    async def _pre_process(self, state: dict) -> dict:
        if self.sandbox and state.get('workspace_files'):
            state['raw_test_results'] = self._run_tests(state)
        return state

    def with_sandbox(self, sandbox: DockerSandbox):
        self.sandbox = sandbox
        return self
