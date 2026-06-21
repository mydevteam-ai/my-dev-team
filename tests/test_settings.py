import argparse
from pathlib import Path
import pytest
from devteam.settings import Settings, Coerced, CoercedPath


def test_coerced_default_and_get_set():
    class Holder:
        value = Coerced(10)
    h = Holder()
    assert h.value == 10
    h.value = '42'
    assert h.value == 42  # coerced to int


def test_coerced_none_passthrough():
    class Holder:
        value = Coerced(None, str)
    h = Holder()
    assert h.value is None
    h.value = None
    assert h.value is None


def test_coerced_already_correct_type():
    class Holder:
        value = Coerced(1)
    h = Holder()
    h.value = 5
    assert h.value == 5


def test_coerced_cli_arg_resolution():
    class Holder:
        no_docker = Coerced(False, cli=True)
        custom = Coerced(False, cli='other_name')
        plain = Coerced(False)
    assert Holder.no_docker.cli_arg == 'no_docker'
    assert Holder.custom.cli_arg == 'other_name'
    assert Holder.plain.cli_arg is None


def test_coerced_path_expanduser():
    class Holder:
        path = CoercedPath('~/data')
    h = Holder()
    h.path = '~/myfolder'
    assert isinstance(h.path, Path)
    assert '~' not in str(h.path)


def test_class_access_returns_descriptor():
    assert isinstance(Settings.workspace_dir, CoercedPath)


def test_apply_args_sets_values():
    s = Settings()
    args = argparse.Namespace(no_docker=True, ask_approval=True, ask_all=False,
                              no_rag=False, max_revisions=5, rag_collection=None,
                              no_ask=False, no_complexity_routing=False, console=True,
                              skills=None)
    s.apply_args(args)
    assert s.no_docker is True
    assert s.ask_approval is True
    assert s.max_revision_count == 5
    assert s.console is True


def test_apply_args_cli_invert():
    s = Settings()
    args = argparse.Namespace(no_rag=True, no_docker=False, ask_approval=False,
                              ask_all=False, max_revisions=None, rag_collection=None,
                              no_ask=False, no_complexity_routing=False, console=False,
                              skills=None)
    s.apply_args(args)
    # rag_enabled has cli='no_rag' cli_invert=True -> no_rag True means rag disabled.
    assert s.rag_enabled is False


def test_load_from_config_file(tmp_path):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text('provider: groq\nllm timeout: 99\nrpm: 5\n', encoding='utf-8')
    s = Settings()
    s.load(cfg)
    assert s.provider == 'groq'
    assert s.llm_timeout == 99
    assert s.rpm == 5


def test_load_missing_file_is_noop(tmp_path):
    s = Settings()
    s.load(tmp_path / 'ghost.yaml')  # does not raise
    assert s.provider == 'ollama'


def test_load_ignores_unknown_keys(tmp_path):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text('unknown_setting: 1\nprovider: openai\n', encoding='utf-8')
    s = Settings()
    s.load(cfg)
    assert s.provider == 'openai'


def test_tools_config_dir_derived():
    s = Settings()
    assert s.tools_config_dir == s.config_dir / 'tools'
