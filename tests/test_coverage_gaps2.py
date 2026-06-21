import sys
import types
import zipfile
from pathlib import Path
import pytest
from devteam.utils import workspace
from devteam.utils.sanitizer import normalize_workspace_content
from devteam.utils.llm_factory import LLMFactory


# =====================================================================
# workspace.hydrate_workspace
# =====================================================================

def test_hydrate_workspace_from_directory(tmp_path):
    seed = tmp_path / 'seed'
    seed.mkdir()
    (seed / 'a.py').write_text('content', encoding='utf-8')
    live = tmp_path / 'live'
    workspace.hydrate_workspace(str(seed), live)
    assert (live / 'a.py').read_text(encoding='utf-8') == 'content'


def test_hydrate_workspace_from_zip(tmp_path):
    archive = tmp_path / 'seed.zip'
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('b.py', 'zipped content')
    live = tmp_path / 'live'
    workspace.hydrate_workspace(str(archive), live)
    assert (live / 'b.py').read_text(encoding='utf-8') == 'zipped content'


def test_read_workspace_file_excluded():
    out = workspace.read_workspace_file('.env', '/some/path')
    assert 'Access denied' in out


def test_read_workspace_file_outside_root(workspace_dir):
    out = workspace.read_workspace_file('../escape.py', workspace_dir)
    assert 'File not found' in out


# =====================================================================
# sanitizer.normalize_workspace_content branches
# =====================================================================

def test_normalize_no_escapes_passthrough():
    text = "def f():\n    return 1\n"
    assert normalize_workspace_content(text) == text


def test_normalize_fully_escaped():
    text = "line1\\nline2\\nline3"
    out = normalize_workspace_content(text)
    assert '\\n' not in out
    assert out == "line1\nline2\nline3"


def test_normalize_double_blank_line_escape():
    text = "head real\nbody\\n\\ntail"
    out = normalize_workspace_content(text)
    assert '\\n' not in out


def test_normalize_crlf_escapes():
    text = "a\\r\\nb\\r\\nc\\r\\nd\\r\\ne"
    out = normalize_workspace_content(text)
    assert '\\r\\n' not in out


def test_normalize_keeps_sparse_escapes():
    # Real newlines dominate; a single escaped \n is left untouched.
    text = "real\nlines\nhere\nwith one \\n literal"
    assert normalize_workspace_content(text) == text


# =====================================================================
# llm_factory: every provider's missing-package ImportError branch
# =====================================================================

@pytest.mark.parametrize('provider,module,hint', [
    ('groq', 'langchain_groq', 'langchain-groq'),
    ('anthropic', 'langchain_anthropic', 'langchain-anthropic'),
    ('openai', 'langchain_openai', 'langchain-openai'),
    ('google', 'langchain_google_genai', 'langchain-google-genai'),
    ('mistral', 'langchain_mistralai', 'langchain-mistralai'),
    ('deepseek', 'langchain_openai', 'langchain-openai'),
    ('grok', 'langchain_openai', 'langchain-openai'),
    ('azure-openai', 'langchain_openai', 'langchain-openai'),
    ('azure-anthropic', 'langchain_openai', 'langchain-openai'),
])
def test_instantiate_import_errors(provider, module, hint, monkeypatch):
    monkeypatch.setitem(sys.modules, module, None)  # force ImportError
    factory = LLMFactory(provider)
    with pytest.raises(ImportError, match=hint):
        factory._instantiate({'id': 'x'}, provider, 0.1, node_name='n', json_mode=False)
