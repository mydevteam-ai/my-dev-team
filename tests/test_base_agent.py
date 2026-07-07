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

def _mock_factory(agent, model_entry):
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    agent.llm_factory = MagicMock()
    agent.llm_factory.create.return_value = llm
    agent.llm_factory.select_model.return_value = model_entry
    return agent.llm_factory


FRONTIER_ENTRY = {'id': 'frontier', 'capabilities': {
    'structured-output': 0.95, 'reasoning': 0.98, 'code-generation': 0.97}}


def test_get_chain_caches_per_complexity():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    factory = _mock_factory(agent, FRONTIER_ENTRY)
    chain1 = agent._get_chain(None)
    chain2 = agent._get_chain(None)
    assert chain1 is chain2
    assert factory.create.call_count == 1


def test_get_chain_passes_selected_model_to_create():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    factory = _mock_factory(agent, FRONTIER_ENTRY)
    agent._get_chain('high')
    factory.select_model.assert_called_once_with({'reasoning': 1.0}, complexity='high')
    assert factory.create.call_args.kwargs['model'] is FRONTIER_ENTRY


def test_get_chain_records_routed_provider():
    # A compound provider's entries carry their real backend, so the rate
    # limiter charges e.g. a `free` run's Groq calls to the Groq budget.
    agent = CodeReviewer(make_config(), "p", "reviewer")
    factory = _mock_factory(agent, {**FRONTIER_ENTRY, 'provider': 'groq'})
    factory.provider = 'free'
    agent._get_chain(None)
    assert agent._chain_providers['_default'] == 'groq'


def test_get_chain_provider_falls_back_to_factory():
    agent = CodeReviewer(make_config(), "p", "reviewer")
    factory = _mock_factory(agent, FRONTIER_ENTRY)
    factory.provider = 'ollama'
    agent._get_chain('high')
    assert agent._chain_providers['high'] == 'ollama'


def test_get_chain_steers_low_scoring_model():
    agent = CodeReviewer(make_config(), "system text", "reviewer")
    _mock_factory(agent, {'id': 'tiny', 'capabilities': {'reasoning': 0.3}})
    chain = agent._get_chain(None)
    system = chain.first.messages[0].prompt.template
    assert system.startswith('system text')
    assert '## Model-specific guidance' in system
    assert 'single tool call' in system


def test_get_chain_leaves_strong_model_prompt_untouched():
    agent = CodeReviewer(make_config(), "system text", "reviewer")
    _mock_factory(agent, FRONTIER_ENTRY)
    chain = agent._get_chain(None)
    assert chain.first.messages[0].prompt.template == 'system text'


def test_build_prompt_escapes_braces_in_steering():
    agent = CodeReviewer(make_config(), "system text", "reviewer")
    prompt = agent._build_prompt('## Guidance\n\n- emit {"key": "value"} only')
    template = prompt.messages[0].prompt.template
    assert '{{"key": "value"}}' in template
    # The escaped template still renders, with the braces restored.
    rendered = prompt.invoke({'messages': []})
    assert '{"key": "value"}' in rendered.messages[0].content


# =====================================================================
# _resolve_includes / from_config
# =====================================================================

def _make_partial(tmp_path, name, text):
    (tmp_path / 'partials').mkdir(exist_ok=True)
    (tmp_path / 'partials' / f'{name}.md').write_text(text, encoding='utf-8')


def test_resolve_includes_inlines_partial(tmp_path):
    _make_partial(tmp_path, 'snippet', "---\nname: snippet\n---\nINCLUDED BODY")
    out = BaseAgent._resolve_includes("Before {{ include snippet }} After", tmp_path)
    assert 'INCLUDED BODY' in out
    assert 'Before' in out and 'After' in out


def test_resolve_includes_normalises_path_and_suffix(tmp_path):
    _make_partial(tmp_path, 'snippet', "BODY")
    assert BaseAgent._resolve_includes("{{ include snippet.md }}", tmp_path) == 'BODY'
    assert BaseAgent._resolve_includes("{{ include partials/snippet.md }}", tmp_path) == 'BODY'


def test_resolve_includes_falls_back_to_base_dir(tmp_path):
    # A config may inherit a full agent prompt; frontmatter is stripped.
    (tmp_path / 'other-agent.md').write_text("---\nrole: X\n---\nAGENT PROMPT", encoding='utf-8')
    assert BaseAgent._resolve_includes("{{ include other-agent }}", tmp_path) == 'AGENT PROMPT'


def test_resolve_includes_conditional_skipped(tmp_path, monkeypatch):
    _make_partial(tmp_path, 'cond', "CONDITIONAL")
    monkeypatch.setattr(settings, 'no_docker', False)
    out = BaseAgent._resolve_includes("{{ include cond if no_docker }}", tmp_path)
    assert 'CONDITIONAL' not in out


def test_resolve_includes_conditional_included(tmp_path, monkeypatch):
    _make_partial(tmp_path, 'cond', "CONDITIONAL")
    monkeypatch.setattr(settings, 'no_docker', True)
    out = BaseAgent._resolve_includes("{{ include cond if no_docker }}", tmp_path)
    assert 'CONDITIONAL' in out


def test_resolve_includes_negated_conditional(tmp_path, monkeypatch):
    _make_partial(tmp_path, 'cond', "CONDITIONAL")
    monkeypatch.setattr(settings, 'no_docker', False)
    assert 'CONDITIONAL' in BaseAgent._resolve_includes("{{ include cond if not no_docker }}", tmp_path)
    monkeypatch.setattr(settings, 'no_docker', True)
    assert 'CONDITIONAL' not in BaseAgent._resolve_includes("{{ include cond if not no_docker }}", tmp_path)


def test_resolve_includes_missing_partial_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        BaseAgent._resolve_includes("{{ include ghost }}", tmp_path)


def test_resolve_includes_traversal_normalised_away(tmp_path):
    # A leading path is stripped, so an include can never escape the agents dir.
    (tmp_path.parent / 'secret.md').write_text("SECRET", encoding='utf-8')
    with pytest.raises(FileNotFoundError):
        BaseAgent._resolve_includes("{{ include ../secret }}", tmp_path)


def test_resolve_includes_nested(tmp_path):
    _make_partial(tmp_path, 'outer', "A {{ include inner }} B")
    _make_partial(tmp_path, 'inner', "X")
    assert BaseAgent._resolve_includes("{{ include outer }}", tmp_path) == 'A X B'


def test_resolve_includes_cycle_rejected(tmp_path):
    _make_partial(tmp_path, 'loop', "{{ include loop }}")
    with pytest.raises(ValueError, match="cyclic"):
        BaseAgent._resolve_includes("{{ include loop }}", tmp_path)


def test_from_config_strips_unrendered_placeholders():
    # The unified prompt-body conventions (TODO 1.3): a shared body may carry
    # {{tools}}/{{skills}}/{{environment}} for the loader that renders them;
    # this loader has no renderer, so they must vanish before templating.
    path = settings.config_dir / 'agents' / 'placeholder_test_agent.md'
    path.write_text(
        "---\nrole: X\n---\nA {{tools}} B {{ skills }} C {{environment}} D",
        encoding='utf-8',
    )
    try:
        agent = CodeReviewer.from_config('reviewer', 'placeholder_test_agent.md')
        assert '{{' not in agent.prompt_template
        assert 'A' in agent.prompt_template and 'D' in agent.prompt_template
    finally:
        path.unlink()


def test_every_agent_prompt_carries_untrusted_data_guard():
    # TODO 2.1: the shared prompt-injection guard must reach every agent.
    agents_dir = settings.config_dir / 'agents'
    for md in agents_dir.glob('*.md'):
        body = md.read_text(encoding='utf-8').split('---', 2)[2]
        prompt = BaseAgent._resolve_includes(body, agents_dir)
        assert 'untrusted data' in prompt, f'{md.name} lacks the untrusted-data guard'


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
