import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from langchain_core.messages import AIMessage
from devteam import settings
from devteam.agents.base_agent import BaseAgent, NoToolCallError
from devteam.agents.code_reviewer import CodeReviewer
from devteam.agents.qa_engineer import QAEngineer
from devteam.agents.qa_final import FinalQAEngineer
from devteam.agents.intermediate_tools import IntermediateTools
from devteam.state import ProjectState, TaskContext


def make_config(inputs=None, tools=None):
    cfg = {'role': 'A', 'name': 'a', 'capabilities': ['reasoning'],
           'temperature': 0.2, 'inputs': inputs or []}
    if tools is not None:
        cfg['tools'] = tools
    return cfg


# =====================================================================
# IntermediateTools
# =====================================================================

class _ToolAgent(IntermediateTools):
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('tool-agent')


class TestIntermediateTools:
    def test_tools_resolves_registry_schema(self):
        agent = _ToolAgent(make_config(tools=['ReadFile']))
        from devteam.tools.schemas import ReadFile
        assert ReadFile in agent.tools

    def test_tools_resolves_agent_schema(self):
        agent = _ToolAgent(make_config(tools=['ApproveCode']))
        from devteam.agents.schemas import ApproveCode
        assert ApproveCode in agent.tools

    def test_tools_skips_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, 'rag_enabled', False)
        agent = _ToolAgent(make_config(tools=['RetrieveContext']))
        from devteam.tools.schemas import RetrieveContext
        assert RetrieveContext not in agent.tools

    def test_tools_warns_on_unknown(self):
        agent = _ToolAgent(make_config(tools=['NoSuchTool']))
        assert agent.tools == []

    def test_handle_intermediate_tool_unknown_returns_none(self):
        agent = _ToolAgent(make_config())
        result = asyncio.run(agent._handle_intermediate_tools('Unknown', {}, ProjectState()))
        assert result is None

    def test_handle_intermediate_tool_disabled_with_message(self, monkeypatch):
        monkeypatch.setattr(settings, 'no_ask', True)
        agent = _ToolAgent(make_config())
        result = asyncio.run(agent._handle_intermediate_tools(
            'AskClarification', {'question': 'q'}, ProjectState()))
        assert 'DISABLED' in result

    def test_handle_intermediate_tool_no_handler_returns_none(self):
        agent = _ToolAgent(make_config())
        # ApproveCode is registered as an agent schema with no handler -> not in registry.
        result = asyncio.run(agent._handle_intermediate_tools(
            'ReadFile', {'path': 'x'}, ProjectState(workspace_path='')))
        assert isinstance(result, str)  # handler runs, returns "file not found" text


# =====================================================================
# base_agent: _parse_outputs / _invoke_llm timeout
# =====================================================================

def test_parse_outputs_no_tool_call_raises():
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    resp = MagicMock()
    resp.tool_calls = []
    with pytest.raises(NoToolCallError):
        agent._parse_outputs(resp)


def test_invoke_llm_timeout(monkeypatch):
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())
    agent._chain_cache['_default'] = chain
    monkeypatch.setattr(settings, 'llm_timeout', 1)
    with pytest.raises(TimeoutError, match="timed out"):
        asyncio.run(agent._invoke_llm())


def test_invoke_llm_waits_for_rate_limiter():
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=AIMessage(content='ok'))
    agent._chain_cache['_default'] = chain
    agent._chain_providers['_default'] = 'groq'
    agent.rate_limiter = MagicMock()
    agent.rate_limiter.wait_if_needed = AsyncMock()
    asyncio.run(agent._invoke_llm())
    agent.rate_limiter.wait_if_needed.assert_awaited_once_with('groq')


def _fake_429(message='rate limited: try again in 2s'):
    exc = Exception(message)
    exc.status_code = 429
    return exc


def test_invoke_llm_retries_429_after_suggested_delay(monkeypatch):
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(side_effect=[_fake_429(), AIMessage(content='ok')])
    agent._chain_cache['_default'] = chain
    sleep_mock = AsyncMock()
    monkeypatch.setattr('devteam.agents.base_agent.asyncio.sleep', sleep_mock)
    response = asyncio.run(agent._invoke_llm())
    assert response.content == 'ok'
    assert chain.ainvoke.await_count == 2
    sleep_mock.assert_awaited_once()
    assert sleep_mock.await_args.args[0] == pytest.approx(2.25)  # suggested 2s + buffer


def test_invoke_llm_reacquires_throttle_slot_per_attempt(monkeypatch):
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(side_effect=[_fake_429(), AIMessage(content='ok')])
    agent._chain_cache['_default'] = chain
    agent._chain_providers['_default'] = 'groq'
    agent.rate_limiter = MagicMock()
    agent.rate_limiter.wait_if_needed = AsyncMock()
    monkeypatch.setattr('devteam.agents.base_agent.asyncio.sleep', AsyncMock())
    asyncio.run(agent._invoke_llm())
    assert agent.rate_limiter.wait_if_needed.await_count == 2


def test_invoke_llm_gives_up_after_capped_429_retries(monkeypatch):
    from devteam.utils.rate_limiter import MAX_RATE_LIMIT_RETRIES
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(side_effect=_fake_429())
    agent._chain_cache['_default'] = chain
    monkeypatch.setattr('devteam.agents.base_agent.asyncio.sleep', AsyncMock())
    with pytest.raises(Exception, match='rate limited'):
        asyncio.run(agent._invoke_llm())
    assert chain.ainvoke.await_count == MAX_RATE_LIMIT_RETRIES + 1


def test_invoke_llm_non_429_raises_immediately(monkeypatch):
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    chain = MagicMock()
    chain.ainvoke = AsyncMock(side_effect=ValueError('schema mismatch'))
    agent._chain_cache['_default'] = chain
    sleep_mock = AsyncMock()
    monkeypatch.setattr('devteam.agents.base_agent.asyncio.sleep', sleep_mock)
    with pytest.raises(ValueError):
        asyncio.run(agent._invoke_llm())
    assert chain.ainvoke.await_count == 1
    sleep_mock.assert_not_awaited()


def test_with_tool_reminder_lists_tools():
    agent = CodeReviewer(make_config(tools=['ApproveCode', 'ReportIssues']), 'p', 'reviewer')
    reminded = agent._with_tool_reminder([])
    assert 'ApproveCode' in reminded[-1].content


# =====================================================================
# code_reviewer / qa_final map_tool
# =====================================================================

def test_code_reviewer_map_tool_report_issues():
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    out = agent._map_tool_to_output('ReportIssues', {'feedback': '- bug'})
    assert out.review_feedback == '- bug'


def test_code_reviewer_map_tool_unexpected():
    agent = CodeReviewer(make_config(), 'p', 'reviewer')
    with pytest.raises(ValueError):
        agent._map_tool_to_output('Bogus', {})


def test_final_qa_map_tool_approve():
    agent = FinalQAEngineer(make_config(), 'p', 'final_qa')
    assert agent._map_tool_to_output('ApproveCode', {}).test_results == 'PASSED'


def test_final_qa_map_tool_report():
    agent = FinalQAEngineer(make_config(), 'p', 'final_qa')
    out = agent._map_tool_to_output('ReportIssues', {'feedback': 'integration bug'})
    assert out.test_results == 'integration bug'


def test_final_qa_map_tool_unexpected():
    agent = FinalQAEngineer(make_config(), 'p', 'final_qa')
    with pytest.raises(ValueError):
        agent._map_tool_to_output('Bogus', {})


# =====================================================================
# qa_engineer _run_tests / _pre_process
# =====================================================================

def test_qa_run_tests_invokes_sandbox(workspace_dir):
    agent = QAEngineer(make_config(), 'p', 'qa')
    sandbox = MagicMock()
    sandbox.run_tests.return_value = '✅ Tests Passed'
    agent.sandbox = sandbox
    state = ProjectState(workspace_path=workspace_dir, runtime='python')
    result = agent._run_tests(state)
    assert 'Passed' in result
    sandbox.run_tests.assert_called_once()


def test_qa_pre_process_runs_tests_when_files_present(workspace_dir):
    agent = QAEngineer(make_config(), 'p', 'qa')
    sandbox = MagicMock()
    sandbox.run_tests.return_value = 'sandbox results'
    agent.sandbox = sandbox
    state = ProjectState(workspace_path=workspace_dir)
    out = asyncio.run(agent._pre_process(state))
    assert out.task_context.raw_test_results == 'sandbox results'


def test_qa_pre_process_noop_without_sandbox(workspace_dir):
    agent = QAEngineer(make_config(), 'p', 'qa')
    state = ProjectState(workspace_path=workspace_dir)
    out = asyncio.run(agent._pre_process(state))
    assert out.task_context.raw_test_results == ''


# =====================================================================
# console_logger _describe_message
# =====================================================================

def test_describe_message_with_tool_calls():
    from devteam.extensions.console_logger import _describe_message
    msg = MagicMock()
    msg.type = 'ai'
    msg.tool_calls = [{'name': 'X'}]
    assert _describe_message(msg) == 'ai+tool_call'


def test_describe_message_plain():
    from devteam.extensions.console_logger import _describe_message
    msg = MagicMock(spec=['type'])
    msg.type = 'human'
    assert _describe_message(msg) == 'human'


def test_format_value_messages_and_drafts():
    from devteam.extensions.console_logger import _format_value
    assert _format_value('messages', []) == '[]'
    out = _format_value('developer_drafts', {'dev': {'a.py': 'x'}})
    assert 'developer(s)' in out
    assert _format_value('developer_drafts', {'dev': {}}) == '{}'


def test_format_value_task_context_summary():
    from devteam.extensions.console_logger import _format_value
    tc = TaskContext(current_agent='dev', current_task_name='A',
                     developer_drafts={'dev': {'a.py': 'x'}})
    out = _format_value('task_context', tc)
    assert 'current_agent' in out


def test_format_value_empty_task_context():
    from devteam.extensions.console_logger import _format_value
    assert _format_value('task_context', TaskContext()) == '(empty)'


# =====================================================================
# tasks dependencies section + extractor edge cases
# =====================================================================

def test_task_to_markdown_with_dependencies():
    from devteam.utils.tasks import task_to_markdown
    out = task_to_markdown({'task_name': 'B', 'user_story': 'us',
                            'acceptance_criteria': ['c'], 'dependencies': ['A'],
                            'complexity': 'high'}, 2)
    assert '### Dependencies' in out
    assert '- A' in out
    assert 'Complexity' in out


def test_task_to_markdown_name_starting_with_task():
    from devteam.utils.tasks import task_to_markdown
    out = task_to_markdown({'task_name': 'Task X already named'}, 1)
    assert '## Task X already named' in out


def test_extractor_no_content_passthrough():
    from devteam.tools.extractor import coerce_tool_calls
    msg = AIMessage(content='')
    assert coerce_tool_calls(msg) is msg


def test_extractor_invalid_json_returns_original():
    from devteam.tools.extractor import coerce_tool_calls
    msg = AIMessage(content='not json at all {broken')
    assert coerce_tool_calls(msg) is msg


def test_extractor_fenced_json():
    from devteam.tools.extractor import coerce_tool_calls
    msg = AIMessage(content='```json\n{"name": "ApproveCode", "arguments": {}}\n```')
    out = coerce_tool_calls(msg)
    assert out.tool_calls[0]['name'] == 'ApproveCode'


# =====================================================================
# rag successful retrieve path
# =====================================================================

def test_retrieve_context_success(monkeypatch):
    from devteam.tools import rag
    monkeypatch.setattr(rag, '_resolve_source', lambda s: ('http://x', 'qdrant-find', {}))

    class FakeItem:
        text = 'chunk text'

    class FakeResult:
        content = [FakeItem()]

    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def initialize(self): pass
        async def call_tool(self, tool, args): return FakeResult()

    class FakeClient:
        async def __aenter__(self): return (None, None, None)
        async def __aexit__(self, *a): return False

    import mcp.client.streamable_http as sh
    import mcp as mcp_mod
    monkeypatch.setattr(sh, 'streamable_http_client', lambda url: FakeClient(), raising=False)
    monkeypatch.setattr(mcp_mod, 'ClientSession', lambda r, w: FakeSession(), raising=False)
    monkeypatch.setattr(settings, 'rag_collection', '', raising=False)

    result = asyncio.run(rag.retrieve_context('query'))
    assert 'chunk text' in result


def test_retrieve_context_no_documents(monkeypatch):
    from devteam.tools import rag
    monkeypatch.setattr(rag, '_resolve_source', lambda s: ('http://x', 'qdrant-find', {}))

    class FakeResult:
        content = []

    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def initialize(self): pass
        async def call_tool(self, tool, args): return FakeResult()

    class FakeClient:
        async def __aenter__(self): return (None, None, None)
        async def __aexit__(self, *a): return False

    import mcp.client.streamable_http as sh
    import mcp as mcp_mod
    monkeypatch.setattr(sh, 'streamable_http_client', lambda url: FakeClient(), raising=False)
    monkeypatch.setattr(mcp_mod, 'ClientSession', lambda r, w: FakeSession(), raising=False)

    result = asyncio.run(rag.retrieve_context('query'))
    assert 'No relevant documents' in result
