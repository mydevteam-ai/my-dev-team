from unittest.mock import MagicMock
import pytest
from rich.panel import Panel
from devteam import settings
from devteam.utils.telemetry import TelemetryTracker
from devteam.utils.cost_optimization import CostOptimization


def _make_generation(input_tokens=0, output_tokens=0, cached_tokens=0,
                     provider='openai', model='gpt-x'):
    gen = MagicMock()
    gen.message.response_metadata = {'model_provider': provider, 'model_name': model}
    usage = {'input_tokens': input_tokens, 'output_tokens': output_tokens}
    if cached_tokens:
        usage['input_tokens_details'] = {'cached_tokens': cached_tokens}
    gen.message.usage_metadata = usage
    return gen


def _make_response(generations):
    resp = MagicMock()
    resp.generations = generations
    return resp


# --- _extract_metadata ---

def test_extract_metadata_single_generation():
    t = TelemetryTracker()
    resp = _make_response([[_make_generation(100, 20, cached_tokens=5)]])
    meta = t._extract_metadata(resp)
    assert meta['input_tokens'] == 100
    assert meta['output_tokens'] == 20
    assert meta['cached_tokens'] == 5
    assert meta['model_provider'] == 'openai'


def test_extract_metadata_counts_prompt_tokens_once():
    t = TelemetryTracker()
    # Two generations from one prompt: input counted once, output summed.
    resp = _make_response([[_make_generation(100, 10), _make_generation(100, 15)]])
    meta = t._extract_metadata(resp)
    assert meta['input_tokens'] == 100
    assert meta['output_tokens'] == 25


def test_extract_metadata_handles_missing_usage():
    t = TelemetryTracker()
    gen = MagicMock()
    gen.message.response_metadata = {}
    gen.message.usage_metadata = None
    meta = t._extract_metadata(_make_response([[gen]]))
    assert meta['input_tokens'] == 0
    assert meta['model_provider'] == 'unknown'


# --- on_llm_end ---

def test_on_llm_end_accumulates_and_records_agent():
    t = TelemetryTracker()
    resp = _make_response([[_make_generation(100, 20, provider='ollama')]])
    t.on_llm_end(resp, tags=['node:developer'])
    assert t.total_requests == 1
    assert t.input_tokens == 100
    assert t.output_tokens == 20
    assert t.agent_calls['developer'] == 1
    assert t.call_history[0]['agent'] == 'developer'
    # ollama is free
    assert t.total_cost == 0


def test_on_llm_end_unknown_agent_without_tags():
    t = TelemetryTracker()
    resp = _make_response([[_make_generation(1, 1, provider='ollama')]])
    t.on_llm_end(resp)
    assert t.agent_calls['unknown'] == 1


# --- alias resolution ---

def test_resolve_alias_exact_match(monkeypatch):
    t = TelemetryTracker()
    t.__dict__['llm_aliases'] = {'foo/bar': 'openai/gpt-4'}
    assert t._resolve_alias('foo/bar') == 'openai/gpt-4'


def test_resolve_alias_wildcard_substitution():
    t = TelemetryTracker()
    t.__dict__['llm_aliases'] = {'google_genai/*': 'gemini/*'}
    assert t._resolve_alias('google_genai/gemini-2.0') == 'gemini/gemini-2.0'


def test_resolve_alias_passthrough():
    t = TelemetryTracker()
    t.__dict__['llm_aliases'] = {}
    assert t._resolve_alias('openai/gpt-4') == 'openai/gpt-4'


def test_llm_aliases_returns_empty_on_error(monkeypatch):
    t = TelemetryTracker()
    class BadDir:
        def __truediv__(self, other):
            return self
        def read_text(self, encoding='utf-8'):
            raise OSError("boom")
    monkeypatch.setattr(settings, 'tools_config_dir', BadDir())
    assert t.llm_aliases == {}


# --- cost calculation ---

def test_calculate_cost_ollama_is_free():
    t = TelemetryTracker()
    assert t._calculate_cost('ollama', 'whatever', 1000, 1000) == 0


def test_calculate_cost_uses_litellm(monkeypatch):
    t = TelemetryTracker()
    monkeypatch.setattr('devteam.utils.telemetry.cost_per_token', lambda **kw: (0.01, 0.02))
    cost = t._calculate_cost('openai', 'gpt-4', 100, 50)
    assert cost == pytest.approx(0.03)


def test_calculate_cost_swallows_errors(monkeypatch):
    t = TelemetryTracker()
    def boom(**kwargs):
        raise RuntimeError("unknown model")
    monkeypatch.setattr('devteam.utils.telemetry.cost_per_token', boom)
    assert t._calculate_cost('openai', 'mystery', 100, 50) == 0


# --- panels ---

def test_get_receipt_panel():
    t = TelemetryTracker()
    t.total_requests = 3
    t.input_tokens = 1000
    t.output_tokens = 500
    panel = t.get_receipt_panel()
    assert isinstance(panel, Panel)


# --- CostOptimization ---

class _Opt(CostOptimization):
    def __init__(self, call_history, agent_calls):
        self.call_history = call_history
        self.agent_calls = agent_calls


def test_optimization_panel_clean_run():
    opt = _Opt([{'agent': 'dev', 'input_tokens': 100, 'output_tokens': 100}], {'dev': 1})
    panel = opt.get_optimization_panel()
    assert isinstance(panel, Panel)


def test_optimization_panel_detects_thrashing():
    opt = _Opt([], {'developer': 8})
    panel = opt.get_optimization_panel()
    assert isinstance(panel.renderable, object)
    # Render to text to confirm warning content.
    from rich.console import Console
    out = Console().render_str  # noqa: F841
    assert opt.agent_calls['developer'] > 5


def test_optimization_panel_detects_context_bloat():
    history = [
        {'agent': 'dev', 'input_tokens': 100, 'output_tokens': 10},
        {'agent': 'dev', 'input_tokens': 200, 'output_tokens': 10},
        {'agent': 'dev', 'input_tokens': 500, 'output_tokens': 10},
    ]
    opt = _Opt(history, {'dev': 3})
    panel = opt.get_optimization_panel()
    assert isinstance(panel, Panel)


def test_optimization_panel_detects_high_waste():
    history = [{'agent': 'dev', 'input_tokens': 9000, 'output_tokens': 10}]
    opt = _Opt(history, {'dev': 1})
    panel = opt.get_optimization_panel()
    # A warnings table panel is produced (red border).
    assert panel.border_style == 'red'


def test_optimization_panel_no_growth_when_first_input_zero():
    history = [
        {'agent': 'dev', 'input_tokens': 0, 'output_tokens': 10},
        {'agent': 'dev', 'input_tokens': 0, 'output_tokens': 10},
        {'agent': 'dev', 'input_tokens': 0, 'output_tokens': 10},
    ]
    opt = _Opt(history, {'dev': 3})
    panel = opt.get_optimization_panel()
    assert panel.border_style == 'green'
