import sys
import types
from unittest.mock import MagicMock
import pytest
from devteam import settings
from devteam.utils.llm_factory import LLMFactory, get_valid_providers


# --- get_valid_providers ---

def test_get_valid_providers_reads_config():
    providers = get_valid_providers()
    assert 'ollama' in providers
    assert 'anthropic' in providers


def test_get_valid_providers_returns_empty_on_error(monkeypatch):
    class BadPath:
        def __truediv__(self, other):
            return self
        def read_text(self, encoding='utf-8'):
            raise OSError("boom")
    monkeypatch.setattr(settings, 'tools_config_dir', BadPath())
    assert get_valid_providers() == []


# --- construction ---

def test_init_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMFactory('does-not-exist')


def test_init_lowercases_provider():
    factory = LLMFactory('OLLAMA')
    assert factory.provider == 'ollama'


def test_model_map_and_llm_config_cached():
    factory = LLMFactory('ollama')
    assert 'ollama' in factory.model_map
    assert factory.llm_config is factory.llm_config  # cached_property


# --- _select_model ---

def test_select_model_picks_highest_capability_score():
    factory = LLMFactory('ollama')
    # Build a fake provider map to make scoring deterministic.
    factory.__dict__['model_map'] = {
        'ollama': {'models': [
            {'id': 'weak', 'capabilities': {'reasoning': 0.1}},
            {'id': 'strong', 'capabilities': {'reasoning': 0.9}},
        ]}
    }
    chosen = factory._select_model({'reasoning': 1.0})
    assert chosen['id'] == 'strong'


def test_select_model_applies_complexity_fit():
    factory = LLMFactory('ollama')
    factory.__dict__['model_map'] = {
        'ollama': {'models': [
            {'id': 'a', 'capabilities': {'reasoning': 0.8}, 'complexity_fit': {'high': 0.1}},
            {'id': 'b', 'capabilities': {'reasoning': 0.5}, 'complexity_fit': {'high': 1.0}},
        ]}
    }
    # Without complexity, 'a' wins on raw capability.
    assert factory._select_model({'reasoning': 1.0})['id'] == 'a'
    # With high complexity, fit flips the winner to 'b'.
    assert factory._select_model({'reasoning': 1.0}, complexity='high')['id'] == 'b'


def test_select_model_zero_weight_defaults_to_first():
    factory = LLMFactory('ollama')
    factory.__dict__['model_map'] = {
        'ollama': {'models': [
            {'id': 'first', 'capabilities': {}},
            {'id': 'second', 'capabilities': {}},
        ]}
    }
    chosen = factory._select_model({})
    assert chosen['id'] == 'first'


# --- _instantiate dispatch (mock provider SDK modules) ---

def _install_fake_module(monkeypatch, module_name: str, class_name: str):
    """Install a fake langchain provider module exposing a recording class."""
    mod = types.ModuleType(module_name)
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            captured['__class__'] = class_name
        def bind(self, **kwargs):
            captured['bound'] = kwargs
            return self
    FakeChat.__name__ = class_name
    setattr(mod, class_name, FakeChat)
    monkeypatch.setitem(sys.modules, module_name, mod)
    return captured


def test_instantiate_ollama_sets_reasoning(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_ollama', 'ChatOllama')
    monkeypatch.setattr(settings, 'llm_streaming', True)
    factory = LLMFactory('ollama')
    model = {'id': 'qwen', 'thinking': True}
    factory._instantiate(model, 'ollama', 0.1, node_name='dev', json_mode=False, top_k=40, top_p=0.9)
    assert captured['model'] == 'qwen'
    assert captured['reasoning'] is True
    assert captured['top_k'] == 40
    assert captured['top_p'] == 0.9


def test_instantiate_ollama_json_mode_disables_reasoning(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_ollama', 'ChatOllama')
    monkeypatch.setattr(settings, 'llm_streaming', True)
    factory = LLMFactory('ollama')
    factory._instantiate({'id': 'q', 'thinking': True}, 'ollama', 0.1, node_name='n', json_mode=True)
    assert captured['format'] == 'json'
    assert captured['reasoning'] is False


def test_instantiate_groq_json_mode_binds_response_format(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_groq', 'ChatGroq')
    factory = LLMFactory('groq')
    factory._instantiate({'id': 'llama'}, 'groq', 0.0, node_name='n', json_mode=True, top_p=0.5)
    assert captured['bound'] == {'response_format': {'type': 'json_object'}}


def test_instantiate_groq_no_json(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_groq', 'ChatGroq')
    factory = LLMFactory('groq')
    factory._instantiate({'id': 'llama'}, 'groq', 0.0, node_name='n', json_mode=False)
    assert 'bound' not in captured


def test_instantiate_anthropic(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_anthropic', 'ChatAnthropic')
    factory = LLMFactory('anthropic')
    factory._instantiate({'id': 'claude'}, 'anthropic', 0.2, node_name='n', json_mode=False, top_k=5)
    assert captured['model'] == 'claude'
    assert captured['top_k'] == 5


def test_instantiate_openai(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_openai', 'ChatOpenAI')
    factory = LLMFactory('openai')
    factory._instantiate({'id': 'gpt'}, 'openai', 0.2, node_name='n', json_mode=False)
    assert captured['model'] == 'gpt'


def test_instantiate_google(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_google_genai', 'ChatGoogleGenerativeAI')
    factory = LLMFactory('google')
    factory._instantiate({'id': 'gemini'}, 'google', 0.2, node_name='n', json_mode=False)
    assert captured['model'] == 'gemini'


def test_instantiate_mistral(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_mistralai', 'ChatMistralAI')
    factory = LLMFactory('mistral')
    factory._instantiate({'id': 'mistral-large'}, 'mistral', 0.2, node_name='n', json_mode=False)
    assert captured['model'] == 'mistral-large'


def test_instantiate_deepseek_uses_env(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_openai', 'ChatOpenAI')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'secret')
    factory = LLMFactory('deepseek')
    factory._instantiate({'id': 'deepseek-chat'}, 'deepseek', 0.2, node_name='n', json_mode=False)
    assert captured['base_url'] == 'https://api.deepseek.com'


def test_instantiate_grok_uses_env(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_openai', 'ChatOpenAI')
    monkeypatch.setenv('XAI_API_KEY', 'secret')
    factory = LLMFactory('grok')
    factory._instantiate({'id': 'grok-2'}, 'grok', 0.2, node_name='n', json_mode=False)
    assert captured['base_url'] == 'https://api.x.ai/v1'


def test_instantiate_azure_openai(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_openai', 'AzureChatOpenAI')
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://az')
    monkeypatch.setenv('AZURE_OPENAI_API_KEY', 'k')
    factory = LLMFactory('azure-openai')
    factory._instantiate({'id': 'dep'}, 'azure-openai', 0.2, node_name='n', json_mode=False)
    assert captured['azure_endpoint'] == 'https://az'


def test_instantiate_azure_anthropic(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_openai', 'ChatOpenAI')
    monkeypatch.setenv('AZURE_ANTHROPIC_ENDPOINT', 'https://aza')
    monkeypatch.setenv('AZURE_ANTHROPIC_API_KEY', 'k')
    factory = LLMFactory('azure-anthropic')
    factory._instantiate({'id': 'claude'}, 'azure-anthropic', 0.2, node_name='n', json_mode=False)
    assert captured['base_url'] == 'https://aza'


def test_instantiate_unknown_provider_raises():
    factory = LLMFactory('ollama')
    with pytest.raises(ValueError, match="Unsupported provider"):
        factory._instantiate({'id': 'x'}, 'nope', 0.1, node_name='n', json_mode=False)


def test_instantiate_missing_package_raises_helpful_error(monkeypatch):
    monkeypatch.setitem(sys.modules, 'langchain_ollama', None)  # forces ImportError
    factory = LLMFactory('ollama')
    with pytest.raises(ImportError, match="pip install langchain-ollama"):
        factory._instantiate({'id': 'q'}, 'ollama', 0.1, node_name='n', json_mode=False)


# --- create() ---

def test_create_accepts_list_capabilities(monkeypatch):
    _install_fake_module(monkeypatch, 'langchain_ollama', 'ChatOllama')
    factory = LLMFactory('ollama')
    factory.__dict__['model_map'] = {
        'ollama': {'models': [{'id': 'm', 'capabilities': {'reasoning': 1.0}, 'thinking': False}]}
    }
    llm = factory.create(['reasoning'], 0.1, node_name='dev')
    assert llm is not None


def test_create_routes_to_model_provider_field(monkeypatch):
    captured = _install_fake_module(monkeypatch, 'langchain_groq', 'ChatGroq')
    factory = LLMFactory('free')
    factory.__dict__['model_map'] = {
        'free': {'models': [{'id': 'llama', 'provider': 'groq', 'capabilities': {'reasoning': 1.0}}]}
    }
    factory.create({'reasoning': 1.0}, 0.0, node_name='dev', complexity='low')
    assert captured['model'] == 'llama'
