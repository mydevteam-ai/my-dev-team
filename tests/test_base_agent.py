import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from devteam import settings
from devteam.agents.base_agent import BaseAgent, NoToolCallError, ConfigField, _resolve_capabilities
from devteam.agents.code_reviewer import CodeReviewer
from devteam.agents.code_judge import CodeJudge
from devteam.agents.code_analyzer import CodeAnalyzer
from devteam.agents.product_manager import ProductManager
from devteam.agents.qa_engineer import QAEngineer
from devteam.state import ProjectState, TaskContext
from devteam.agents.schemas import (
    CodeJudgeResponse, MigrationAnalysisResponse, MigrationTask,
    ProductManagerResponse, QAEngineerResponse,
)


def make_config(role="TestAgent", inputs=None, **extra):
    cfg = {
        "role": role, "name": role.lower().replace(" ", "_"),
        "capabilities": ["reasoning"], "temperature": 0.2,
        "inputs": inputs or [],
    }
    cfg.update(extra)
    return cfg


# =====================================================================
# ConfigField + capability helpers
# =====================================================================

def test_resolve_capabilities_list():
    assert _resolve_capabilities(['a', 'b']) == {'a': 1.0, 'b': 1.0}


def test_resolve_capabilities_dict():
    assert _resolve_capabilities({'a': 0.5}) == {'a': 0.5}


def test_config_field_descriptor_access_on_class():
    assert isinstance(BaseAgent.temperature, ConfigField)


def test_config_field_defaults_and_transform():
    agent = CodeReviewer(make_config(), "prompt", "reviewer")
    assert agent.temperature == 0.2
    assert agent.complexity_routing is False
    assert agent.complexity_overrides == {}


# =====================================================================
# _build_prompt / data keys / prompt tags
# =====================================================================

def test_build_prompt_includes_human_and_placeholder():
    agent = CodeReviewer(make_config(inputs=['specs', 'messages']), "system text", "reviewer")
    prompt = agent._build_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    # 'specs' becomes a template var; messages handled by placeholder.
    assert 'specs' in agent._data_input_keys()
    assert 'messages' not in agent._data_input_keys()


def test_build_prompt_no_data_keys():
    agent = CodeReviewer(make_config(inputs=[]), "system text", "reviewer")
    prompt = agent._build_prompt()
    assert isinstance(prompt, ChatPromptTemplate)


def test_prompt_tag_uses_handler_tag():
    agent = QAEngineer(make_config(inputs=['workspace_context']), "p", "qa")
    # workspace_context handler is tagged 'workspace'.
    assert agent._prompt_tag('workspace_context') == 'workspace'


def test_prompt_tag_defaults_to_key():
    agent = CodeReviewer(make_config(inputs=['specs']), "p", "reviewer")
    assert agent._prompt_tag('specs') == 'specs'


# =====================================================================
# _input_state_attr / _task_query
# =====================================================================

def test_input_state_attr_reads_task_context_fallback():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    state = ProjectState(task_context=TaskContext(current_task='do work'))
    assert agent._input_state_attr(state, 'current_task') == 'do work'


def test_input_state_attr_empty():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    assert agent._input_state_attr(ProjectState(), 'specs') == ''


def test_task_query_prefers_current_task():
    state = ProjectState(specs='spec', task_context=TaskContext(current_task='task'))
    assert BaseAgent._task_query(state) == 'task'


def test_task_query_falls_back_to_specs():
    state = ProjectState(specs='spec')
    assert BaseAgent._task_query(state) == 'spec'


# =====================================================================
# _repair_tool_call_messages
# =====================================================================

def test_repair_converts_human_after_unanswered_toolcall():
    ai = AIMessage(content='', tool_calls=[{'name': 'X', 'args': {}, 'id': 'tc1'}])
    human = HumanMessage(content='here is your answer')
    repaired = BaseAgent._repair_tool_call_messages([ai, human])
    assert isinstance(repaired[1], ToolMessage)
    assert repaired[1].tool_call_id == 'tc1'


def test_repair_keeps_existing_tool_messages():
    ai = AIMessage(content='', tool_calls=[{'name': 'X', 'args': {}, 'id': 'tc1'}])
    tm = ToolMessage(content='result', tool_call_id='tc1')
    repaired = BaseAgent._repair_tool_call_messages([ai, tm])
    assert repaired == [ai, tm]


def test_repair_passes_through_plain_messages():
    msgs = [HumanMessage(content='hi')]
    assert BaseAgent._repair_tool_call_messages(msgs) == msgs


# =====================================================================
# _resolve_complexity / _resolve_params
# =====================================================================

def test_resolve_complexity_disabled_by_default():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    assert agent._resolve_complexity(ProjectState()) is None


def test_resolve_complexity_task_level(monkeypatch):
    monkeypatch.setattr(settings, 'no_complexity_routing', False)
    agent = CodeReviewer(make_config(complexity_routing=True), "p", "reviewer")
    state = ProjectState(task_context=TaskContext(current_task_complexity='high'))
    assert agent._resolve_complexity(state) == 'high'


def test_resolve_complexity_project_level(monkeypatch):
    monkeypatch.setattr(settings, 'no_complexity_routing', False)
    agent = CodeReviewer(make_config(complexity_routing=True), "p", "reviewer")
    state = ProjectState(project_complexity='medium')
    assert agent._resolve_complexity(state) == 'medium'


def test_resolve_complexity_globally_disabled(monkeypatch):
    monkeypatch.setattr(settings, 'no_complexity_routing', True)
    agent = CodeReviewer(make_config(complexity_routing=True), "p", "reviewer")
    state = ProjectState(project_complexity='high')
    assert agent._resolve_complexity(state) is None


def test_resolve_params_base():
    agent = CodeReviewer(make_config(top_p=0.8), "p", "reviewer")
    temp, extras = agent._resolve_params(None)
    assert temp == 0.2
    assert extras['top_p'] == 0.8


def test_resolve_params_complexity_override():
    cfg = make_config(complexity_overrides={'high': {'temperature': 0.7, 'thinking': True}})
    agent = CodeReviewer(cfg, "p", "reviewer")
    temp, extras = agent._resolve_params('high')
    assert temp == 0.7
    assert extras['thinking'] is True


# =====================================================================
# _get_llm / _get_chain caching
# =====================================================================

def test_get_chain_caches_per_complexity():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    agent.llm_factory = MagicMock()
    agent.llm_factory.create.return_value = llm
    chain1 = agent._get_chain(None)
    chain2 = agent._get_chain(None)
    assert chain1 is chain2
    assert agent.llm_factory.create.call_count == 1


# =====================================================================
# _resolve_includes / from_config
# =====================================================================

def test_resolve_includes_inlines_file(tmp_path):
    (tmp_path / 'snippet.md').write_text("---\nx: 1\n---\nINCLUDED BODY", encoding='utf-8')
    out = BaseAgent._resolve_includes("Before {include 'snippet.md'} After", tmp_path)
    assert 'INCLUDED BODY' in out
    assert 'Before' in out and 'After' in out


def test_resolve_includes_conditional_skipped(tmp_path, monkeypatch):
    (tmp_path / 'cond.md').write_text("CONDITIONAL", encoding='utf-8')
    monkeypatch.setattr(settings, 'no_docker', False)
    out = BaseAgent._resolve_includes("{include 'cond.md' if no_docker}", tmp_path)
    assert 'CONDITIONAL' not in out


def test_resolve_includes_conditional_included(tmp_path, monkeypatch):
    (tmp_path / 'cond.md').write_text("CONDITIONAL", encoding='utf-8')
    monkeypatch.setattr(settings, 'no_docker', True)
    out = BaseAgent._resolve_includes("{include 'cond.md' if no_docker}", tmp_path)
    assert 'CONDITIONAL' in out


def test_resolve_includes_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        BaseAgent._resolve_includes("{include 'ghost.md'}", tmp_path)


def test_resolve_includes_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        BaseAgent._resolve_includes("{include '../secret.md'}", tmp_path)


def test_from_config_reads_real_agent_md():
    agent = ProductManager.from_config('pm', 'product-manager.md')
    assert agent.node_name == 'pm'
    assert agent.prompt_template


def test_from_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        CodeReviewer.from_config('reviewer', 'does-not-exist.md')


def test_from_config_invalid_frontmatter_raises(tmp_path, monkeypatch):
    bad = settings.config_dir / 'agents' / 'bad_test_agent.md'
    bad.write_text("no frontmatter at all", encoding='utf-8')
    try:
        with pytest.raises(ValueError, match="Missing YAML frontmatter"):
            CodeReviewer.from_config('reviewer', 'bad_test_agent.md')
    finally:
        bad.unlink()


def test_from_config_applies_overrides():
    agent = ProductManager.from_config('pm', 'product-manager.md', temperature=0.99, top_k=7)
    assert agent.temperature == 0.99
    assert agent.top_k == 7


# =====================================================================
# process() edge cases not already covered in test_agents.py
# =====================================================================

class _ReviewerHelper:
    def make(self):
        agent = CodeReviewer(make_config(inputs=[]), "p", "reviewer")
        return agent


def _ai(name, args=None):
    msg = MagicMock()
    msg.content = 'text'
    msg.tool_calls = [{'name': name, 'args': args or {}, 'id': 'tc1'}]
    return msg


def test_process_accepts_dict_state():
    agent = CodeReviewer(make_config(inputs=[]), "p", "reviewer")
    agent._invoke_llm = AsyncMock(return_value=_ai('ApproveCode'))
    result = asyncio.run(agent.process({'requirements': 'x'}))
    assert 'error' not in result


def test_process_import_error_returns_error():
    agent = CodeReviewer(make_config(inputs=[]), "p", "reviewer")
    agent._invoke_llm = AsyncMock(side_effect=ImportError("missing pkg"))
    result = asyncio.run(agent.process(ProjectState()))
    assert result['error'] is True
    assert 'missing pkg' in result['error_message']


def test_process_no_tool_call_retries_with_reminder():
    agent = CodeReviewer(make_config(inputs=[]), "p", "reviewer")
    agent.max_retries = 1
    no_tool = MagicMock()
    no_tool.content = 'plain text'
    no_tool.tool_calls = []
    good = _ai('ApproveCode')
    agent._invoke_llm = AsyncMock(side_effect=[no_tool, good])
    result = asyncio.run(agent.process(ProjectState()))
    assert 'error' not in result
    assert agent._invoke_llm.call_count == 2


def test_is_tool_validation_error():
    assert BaseAgent._is_tool_validation_error(Exception("model attempted to call tool foo"))
    assert not BaseAgent._is_tool_validation_error(Exception("network down"))


# =====================================================================
# CodeJudge
# =====================================================================

class TestCodeJudge:
    def _state(self):
        return ProjectState(task_context=TaskContext(developer_drafts={
            'developer_a': {'a.py': 'A'},
            'developer_b': {'b.py': 'B'},
        }))

    def test_input_drafts_formats_all(self):
        agent = CodeJudge(make_config(), "p", "judge")
        out = agent._input_drafts(self._state())
        assert '<draft_0>' in out and '<draft_1>' in out

    def test_update_state_selects_winner(self):
        agent = CodeJudge(make_config(), "p", "judge")
        result = agent._update_state(CodeJudgeResponse(winner_index=1), self._state())
        tc = result['task_context']
        assert tc.winner_developer == 'developer_b'
        assert set(tc.developer_drafts.keys()) == {'developer_b'}

    def test_update_state_hallucinated_index_defaults_to_first(self):
        agent = CodeJudge(make_config(), "p", "judge")
        result = agent._update_state(CodeJudgeResponse(winner_index=99), self._state())
        assert result['task_context'].winner_developer == 'developer_a'


# =====================================================================
# CodeAnalyzer
# =====================================================================

def test_code_analyzer_update_state():
    agent = CodeAnalyzer(make_config(), "p", "analyzer")
    parsed = MigrationAnalysisResponse(
        runtime='python', specs='analysis doc',
        pending_tasks=[MigrationTask(task_name='T1', description='d', acceptance_criteria=['c'])],
    )
    result = agent._update_state(parsed, ProjectState())
    assert result['runtime'] == 'python'
    assert result['specs'] == 'analysis doc'
    assert len(result['pending_tasks']) == 1


# =====================================================================
# ProductManager / QAEngineer map_tool errors
# =====================================================================

def test_pm_map_tool_clarification():
    agent = ProductManager(make_config(), "p", "pm")
    out = agent._map_tool_to_output('AskClarification', {'question': 'what stack?'})
    assert out.clarification_question == 'what stack?'


def test_pm_map_tool_specification():
    agent = ProductManager(make_config(), "p", "pm")
    out = agent._map_tool_to_output('SubmitSpecification',
                                    {'specs': 'S', 'project_complexity': 'low'})
    assert out.specs == 'S'
    assert out.project_complexity == 'low'


def test_pm_map_tool_unexpected_raises():
    agent = ProductManager(make_config(), "p", "pm")
    with pytest.raises(ValueError, match="Unexpected tool call"):
        agent._map_tool_to_output('Bogus', {})


def test_qa_map_tool_unexpected_raises():
    agent = QAEngineer(make_config(), "p", "qa")
    with pytest.raises(ValueError, match="Unexpected tool call"):
        agent._map_tool_to_output('Bogus', {})


def test_qa_input_test_results_uses_raw():
    agent = QAEngineer(make_config(), "p", "qa")
    state = ProjectState(task_context=TaskContext(raw_test_results='sandbox output here'))
    assert 'sandbox output here' in agent._input_test_results(state)


def test_qa_with_sandbox_attaches():
    agent = QAEngineer(make_config(), "p", "qa")
    sentinel = object()
    assert agent.with_sandbox(sentinel) is agent
    assert agent.sandbox is sentinel
