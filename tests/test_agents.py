import asyncio
from unittest.mock import AsyncMock, MagicMock
from devteam.agents.code_reviewer import CodeReviewer
from devteam.agents.developer import SeniorDeveloper
from devteam.agents.product_manager import ProductManager
from devteam.agents.qa_engineer import QAEngineer
from devteam.agents.qa_final import FinalQAEngineer
from devteam.agents.reporter import Reporter
from devteam.agents.system_architect import SystemArchitect
from devteam.state import ProjectState

from devteam.agents.schemas import (
    CodeReviewerResponse,
    DeveloperResponse,
    WorkspaceFile,
    QAEngineerResponse,
    FinalQAResponse,
)

# --- Helpers ---

def make_config(role="TestAgent", inputs=None):
    return {
        "role": role,
        "name": role.lower().replace(" ", "_"),
        "capabilities": ["reasoning"],
        "temperature": 0.2,
        "inputs": inputs or [],
    }

# --- CodeReviewer Tests ---

class TestCodeReviewer:
    def test_build_inputs_with_workspace(self, sample_workspace_files):
        config = make_config("Code Reviewer", ["specs", "current_task"])
        agent = CodeReviewer(config, "prompt {specs} {current_task} {workspace}", "reviewer")
        state = ProjectState(specs="spec", current_task="task", workspace_files=sample_workspace_files)
        inputs = agent._build_inputs(state)
        assert "--- FILE: src/main.py ---" in inputs["workspace"]
        assert "--- FILE: tests/test_main.py ---" in inputs["workspace"]

    def test_build_inputs_no_workspace(self):
        config = make_config("Code Reviewer", [])
        agent = CodeReviewer(config, "prompt {workspace}", "reviewer")
        state = ProjectState()
        inputs = agent._build_inputs(state)
        assert "No files exist" in inputs["workspace"]

    def test_update_state_approved(self):
        config = make_config("Code Reviewer")
        agent = CodeReviewer(config, "prompt", "reviewer")
        parsed = CodeReviewerResponse(review_feedback="APPROVED")
        result = agent._update_state(parsed, ProjectState())
        assert result["review_feedback"] == "APPROVED"
        assert "APPROVED" in result["communication_log"][0]

    def test_update_state_with_changes(self):
        config = make_config("Code Reviewer")
        agent = CodeReviewer(config, "prompt", "reviewer")
        parsed = CodeReviewerResponse(review_feedback="- [main.py] - Bug: missing import")
        result = agent._update_state(parsed, ProjectState())
        assert result["review_feedback"] == "- [main.py] - Bug: missing import"
        assert "REQUESTED CHANGES" in result["communication_log"][0]

    def test_update_state_approved_with_dots(self):
        config = make_config("Code Reviewer")
        agent = CodeReviewer(config, "prompt", "reviewer")
        parsed = CodeReviewerResponse(review_feedback="  APPROVED.  ")
        result = agent._update_state(parsed, ProjectState())
        assert result["review_feedback"] == "APPROVED"

# --- SeniorDeveloper Tests ---

class TestSeniorDeveloper:
    def test_workspace_file_normalizes_fully_escaped_newlines(self):
        file_obj = WorkspaceFile(
            path="tests/test_user_input.py",
            content="import unittest\\n\\nfrom user_input import parse_number\\n",
        )
        assert "\\n" not in file_obj.content
        assert "import unittest\n\nfrom user_input import parse_number\n" == file_obj.content

    def test_workspace_file_preserves_normal_multiline_content(self):
        content = "def add(a, b):\n    return a + b\n"
        file_obj = WorkspaceFile(path="calculator.py", content=content)
        assert file_obj.content == content

    def test_workspace_file_normalizes_heavily_escaped_mixed_content(self):
        content = "'''Doc'''\\n\\ndef parse_number(x):\n    return float(x)\\n"
        file_obj = WorkspaceFile(path="user_input.py", content=content)
        assert "\\n\\n" not in file_obj.content
        assert "'''Doc'''\n\ndef parse_number(x):\n    return float(x)\n" == file_obj.content

    def test_build_inputs_no_workspace(self):
        config = make_config("Developer", ["specs", "current_task"])
        agent = SeniorDeveloper(config, "prompt {specs} {current_task} {workspace}", "developer")
        state = ProjectState(specs="spec", current_task="build it")
        inputs = agent._build_inputs(state)
        assert "No files exist yet" in inputs["workspace"]

    def test_build_inputs_with_workspace(self, sample_workspace_files):
        config = make_config("Developer", ["specs", "current_task"])
        agent = SeniorDeveloper(config, "prompt {specs} {current_task} {workspace}", "developer")
        state = ProjectState(specs="spec", current_task="task", workspace_files=sample_workspace_files)
        inputs = agent._build_inputs(state)
        assert "--- FILE: src/main.py ---" in inputs["workspace"]

    def test_update_state_new_files(self):
        config = make_config("Developer")
        agent = SeniorDeveloper(config, "prompt", "developer")
        parsed = DeveloperResponse(workspace_files=[
            WorkspaceFile(path="src/app.py", content="app code"),
            WorkspaceFile(path="tests/test_app.py", content="test code"),
        ])
        result = agent._update_state(parsed, ProjectState())
        assert "src/app.py" in result["workspace_files"]
        assert "tests/test_app.py" in result["workspace_files"]
        assert result["review_feedback"] == ""
        assert result["test_results"] == ""

    def test_update_state_merges_workspace(self):
        config = make_config("Developer")
        agent = SeniorDeveloper(config, "prompt", "developer")
        parsed = DeveloperResponse(workspace_files=[
            WorkspaceFile(path="new.py", content="new file"),
        ])
        result = agent._update_state(parsed, ProjectState(workspace_files={"old.py": "old code"}))
        assert "old.py" in result["workspace_files"]
        assert "new.py" in result["workspace_files"]

# --- ProductManager Tests ---

class TestProductManager:
    def test_has_correct_schema(self):
        from devteam.agents.schemas import ProductManagerResponse
        config = make_config("Product Manager")
        agent = ProductManager(config, "prompt", "pm")
        assert agent.output_schema is ProductManagerResponse

# --- QAEngineer Tests ---

class TestQAEngineer:
    def test_build_inputs_with_workspace(self, sample_workspace_files):
        config = make_config("QA Engineer", ["specs", "current_task"])
        agent = QAEngineer(config, "prompt {specs} {current_task} {workspace}", "qa")
        state = ProjectState(specs="spec", current_task="task", workspace_files=sample_workspace_files)
        inputs = agent._build_inputs(state)
        assert "--- FILE: src/main.py ---" in inputs["workspace"]

    def test_build_inputs_empty_workspace(self):
        config = make_config("QA Engineer", [])
        agent = QAEngineer(config, "prompt {workspace}", "qa")
        state = ProjectState()
        inputs = agent._build_inputs(state)
        assert "No files exist" in inputs["workspace"]

    def test_update_state_passed(self):
        config = make_config("QA Engineer")
        agent = QAEngineer(config, "prompt", "qa")
        parsed = QAEngineerResponse(test_results="PASSED")
        result = agent._update_state(parsed, ProjectState())
        assert result["test_results"] == "APPROVED"
        assert "APPROVED" in result["communication_log"][0]

    def test_update_state_bugs(self):
        config = make_config("QA Engineer")
        agent = QAEngineer(config, "prompt", "qa")
        parsed = QAEngineerResponse(test_results="Bug found: missing null check")
        result = agent._update_state(parsed, ProjectState())
        assert result["test_results"] == "Bug found: missing null check"
        assert "BUGS FOUND" in result["communication_log"][0]

# --- FinalQAEngineer Tests ---

class TestFinalQAEngineer:
    def test_build_inputs_with_workspace(self, sample_workspace_files):
        config = make_config("Final QA", ["specs"])
        agent = FinalQAEngineer(config, "prompt {specs} {workspace}", "final_qa")
        state = ProjectState(specs="spec", workspace_files=sample_workspace_files)
        inputs = agent._build_inputs(state)
        assert "--- FILE: src/main.py ---" in inputs["workspace"]

    def test_update_state_passed(self):
        config = make_config("Final QA")
        agent = FinalQAEngineer(config, "prompt", "final_qa")
        parsed = FinalQAResponse(test_results="PASSED")
        result = agent._update_state(parsed, ProjectState())
        assert result["test_results"] == "APPROVED"
        assert "APPROVED" in result["communication_log"][0]

    def test_update_state_bugs_sets_integration_task(self):
        config = make_config("Final QA")
        agent = FinalQAEngineer(config, "prompt", "final_qa")
        parsed = FinalQAResponse(test_results="Integration bug in auth")
        result = agent._update_state(parsed, ProjectState())
        assert result["test_results"] == "Integration bug in auth"
        assert "FINAL INTEGRATION" in result["current_task"]

# --- Reporter Tests ---

class TestReporter:
    def test_build_inputs_with_workspace(self, sample_workspace_files):
        config = make_config("Reporter", ["specs"])
        agent = Reporter(config, "prompt {specs} {workspace} {history}", "reporter")
        state = ProjectState(specs="spec", workspace_files=sample_workspace_files, communication_log=["Log entry 1", "Log entry 2"])
        inputs = agent._build_inputs(state)
        assert "--- FILE: src/main.py ---" in inputs["workspace"]
        assert "Log entry 1" in inputs["history"]
        assert "Log entry 2" in inputs["history"]

    def test_build_inputs_empty_workspace(self):
        config = make_config("Reporter", [])
        agent = Reporter(config, "prompt {workspace} {history}", "reporter")
        state = ProjectState()
        inputs = agent._build_inputs(state)
        assert "No files were generated" in inputs["workspace"]

# --- BaseAgent Retry Tests ---

class TestBaseAgentRetry:
    def _make_agent(self, max_retries=2):
        from devteam.agents.schemas import CodeReviewerResponse
        config = make_config("Test Agent", [])
        agent = CodeReviewer(config, "prompt", "reviewer")
        agent.max_retries = max_retries
        return agent

    def _make_ai_message(self, tool_name: str, tool_args: dict):
        msg = MagicMock()
        msg.content = ''
        msg.tool_calls = [{'name': tool_name, 'args': tool_args, 'id': 'tc1'}]
        return msg

    def test_succeeds_on_first_attempt(self):
        agent = self._make_agent()
        ai_msg = self._make_ai_message('ApproveCode', {})
        agent._invoke_llm = AsyncMock(return_value=ai_msg)
        result = asyncio.run(agent.process(ProjectState()))
        assert agent._invoke_llm.call_count == 1
        assert 'error' not in result

    def test_retries_on_failure_then_succeeds(self):
        agent = self._make_agent(max_retries=2)
        ai_msg = self._make_ai_message('ApproveCode', {})
        agent._invoke_llm = AsyncMock(side_effect=[
            ValueError("timeout"),
            ValueError("timeout"),
            ai_msg,
        ])
        result = asyncio.run(agent.process(ProjectState()))
        assert agent._invoke_llm.call_count == 3
        assert 'error' not in result

    def test_returns_error_after_exhausting_retries(self):
        agent = self._make_agent(max_retries=1)
        agent._invoke_llm = AsyncMock(side_effect=ValueError("persistent failure"))
        result = asyncio.run(agent.process(ProjectState()))
        assert agent._invoke_llm.call_count == 2  # 1 attempt + 1 retry
        assert result.get('error') is True
        assert 'persistent failure' in result.get('error_message', '')

# --- ProjectManager Error Recovery Tests ---

class TestProjectManagerErrorRecovery:
    def _make_manager(self):
        from devteam.managers.project_manager import ProjectManager
        return ProjectManager(agents={})

    def test_development_error_skips_task_and_clears_flag(self):
        manager = self._make_manager()
        state = ProjectState(
            current_phase='development',
            current_task_index=2,
            current_task='Build the authentication module',
            error=True,
            error_message='LLM timed out after 120 seconds',
        )
        result = manager._manager_node(state)
        assert result['error'] is False
        assert result['error_message'] == ''
        assert result['current_agent'] == 'officer'
        assert len(result['failed_tasks']) == 1
        assert 'Task 2' in result['failed_tasks'][0]

    def test_planning_error_aborts_workflow(self):
        manager = self._make_manager()
        state = ProjectState(
            current_phase='planning',
            error=True,
            error_message='LLM timed out',
        )
        result = manager._manager_node(state)
        assert result.get('abort_requested') is True
        assert 'error' not in result or result.get('current_agent') is None

    def test_no_error_delegates_to_phase_logic(self):
        manager = self._make_manager()
        state = ProjectState(
            current_phase='development',
            current_agent='developer',
            error=False,
        )
        result = manager._manager_node(state)
        assert result.get('current_agent') == 'reviewer'

# --- SystemArchitect Tests ---

class TestSystemArchitect:
    def test_has_correct_schema(self):
        from devteam.agents.schemas import SystemArchitectResponse
        config = make_config("System Architect")
        agent = SystemArchitect(config, "prompt", "architect")
        assert agent.output_schema is SystemArchitectResponse
