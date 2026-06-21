import argparse
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from devteam import settings
import importlib
from devteam.cli import runtime

cli_main = importlib.import_module('devteam.cli.main')
from devteam.cli.extensions import build_extensions
from devteam.cli.request import ResumeRequest, StartRequest, RunHooks


# =====================================================================
# argument parser & validation
# =====================================================================

class TestParser:
    def test_parser_defaults(self):
        parser = cli_main._build_parser()
        args = parser.parse_args(['project.txt'])
        assert args.project_file == 'project.txt'
        assert args.provider == settings.provider
        assert args.workflow == 'development'

    def test_parser_flags(self):
        parser = cli_main._build_parser()
        args = parser.parse_args(['--resume', 'thread1', '--fanout', '--no-docker'])
        assert args.resume == 'thread1'
        assert args.fanout is True
        assert args.no_docker is True

    def test_mutually_exclusive_ask_flags(self):
        parser = cli_main._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['p.txt', '--ask-all', '--no-ask'])

    def test_apply_config_missing_dir_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            cli_main._apply_config(str(tmp_path / 'nope'))

    def test_apply_config_none_noop(self):
        cli_main._apply_config(None)  # returns without error

    def test_apply_config_valid_dir(self, tmp_path):
        saved = settings.config_dir
        try:
            cli_main._apply_config(str(tmp_path))
            assert settings.config_dir == tmp_path
        finally:
            settings.config_dir = saved


class TestValidateInputs:
    def _parser(self):
        return cli_main._build_parser()

    def test_history_missing_workspace_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        parser = self._parser()
        args = parser.parse_args(['--history', 'ghost'])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_history_existing_ok(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        parser = self._parser()
        args = parser.parse_args(['--history', 'thread1'])
        cli_main._validate_inputs(parser, args)  # no exit

    def test_resume_missing_workspace_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        parser = self._parser()
        args = parser.parse_args(['--resume', 'ghost'])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_project_file_missing_errors(self):
        parser = self._parser()
        args = parser.parse_args(['no_such_file.txt'])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_no_input_errors(self):
        parser = self._parser()
        args = parser.parse_args([])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_seed_with_resume_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        seed = tmp_path / 'seed'
        seed.mkdir()
        parser = self._parser()
        args = parser.parse_args(['--resume', 'thread1', '--seed', str(seed)])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_seed_missing_path_errors(self, tmp_path):
        spec = tmp_path / 'p.txt'
        spec.write_text('x', encoding='utf-8')
        parser = self._parser()
        args = parser.parse_args([str(spec), '--seed', str(tmp_path / 'ghost')])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)

    def test_seed_dir_ok(self, tmp_path):
        spec = tmp_path / 'p.txt'
        spec.write_text('x', encoding='utf-8')
        seed = tmp_path / 'seed'
        seed.mkdir()
        parser = self._parser()
        args = parser.parse_args([str(spec), '--seed', str(seed)])
        cli_main._validate_inputs(parser, args)

    def test_seed_non_zip_file_errors(self, tmp_path):
        spec = tmp_path / 'p.txt'
        spec.write_text('x', encoding='utf-8')
        seed = tmp_path / 'seed.txt'
        seed.write_text('not a zip', encoding='utf-8')
        parser = self._parser()
        args = parser.parse_args([str(spec), '--seed', str(seed)])
        with pytest.raises(SystemExit):
            cli_main._validate_inputs(parser, args)


# =====================================================================
# _build_request
# =====================================================================

class TestBuildRequest:
    def test_resume_request(self):
        parser = cli_main._build_parser()
        args = parser.parse_args(['--resume', 'thread1', '--feedback', 'fix', '--as-node', 'qa'])
        req = cli_main._build_request(args)
        assert isinstance(req, ResumeRequest)
        assert req.resume_thread == 'thread1'
        assert req.feedback == 'fix'
        assert req.feedback_source == 'qa'

    def test_start_request(self, tmp_path):
        spec = tmp_path / 'p.txt'
        spec.write_text('Subject: NEW PROJECT: Cool App\n\nBuild it.', encoding='utf-8')
        parser = cli_main._build_parser()
        args = parser.parse_args([str(spec)])
        req = cli_main._build_request(args)
        assert isinstance(req, StartRequest)
        assert req.project_name == 'Cool App'
        assert req.requirements == 'Build it.'


# =====================================================================
# main() orchestration
# =====================================================================

class TestMain:
    def test_main_azure_already_azure_errors(self, monkeypatch):
        monkeypatch.setattr('sys.argv', ['devteam', 'p.txt', '--provider', 'azure-openai', '--azure'])
        monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
        with pytest.raises(SystemExit):
            cli_main.main()

    def test_main_thinking_without_console_errors(self, monkeypatch):
        monkeypatch.setattr('sys.argv', ['devteam', 'p.txt', '--thinking'])
        monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
        with pytest.raises(SystemExit):
            cli_main.main()

    def test_main_invalid_provider_errors(self, monkeypatch):
        monkeypatch.setattr('sys.argv', ['devteam', 'p.txt', '--provider', 'not-real'])
        monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
        monkeypatch.setattr(cli_main, 'setup_logging', lambda **k: None)
        with pytest.raises(SystemExit):
            cli_main.main()

    def test_main_history_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        monkeypatch.setattr('sys.argv', ['devteam', '--history', 'thread1', '--provider', 'ollama'])
        monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
        monkeypatch.setattr(cli_main, 'setup_logging', lambda **k: None)
        called = {}
        async def fake_show(thread_id):
            called['thread_id'] = thread_id
        monkeypatch.setattr(cli_main, 'show_history', fake_show)
        cli_main.main()
        assert called['thread_id'] == 'thread1'

    def test_main_runs_async_main(self, monkeypatch, tmp_path):
        spec = tmp_path / 'p.txt'
        spec.write_text('Build a thing.', encoding='utf-8')
        monkeypatch.setattr('sys.argv', ['devteam', str(spec), '--provider', 'ollama'])
        monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
        monkeypatch.setattr(cli_main, 'setup_logging', lambda **k: None)
        ran = {}
        async def fake_async_main(req):
            ran['req'] = req
        monkeypatch.setattr(cli_main, 'async_main', fake_async_main)
        cli_main.main()
        assert isinstance(ran['req'], StartRequest)


def test_load_settings_from_argv(monkeypatch, tmp_path):
    cfg = tmp_path / 'cfg.yaml'
    cfg.write_text('provider: groq\n', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['devteam', '--settings', str(cfg)])
    captured = {}
    monkeypatch.setattr(settings, 'load', lambda p=None: captured.setdefault('path', p))
    cli_main._load_settings_from_argv()
    assert captured['path'] == cfg


def test_main_ui_invokes_run_server(monkeypatch):
    monkeypatch.setattr(cli_main, '_load_settings_from_argv', lambda: None)
    monkeypatch.setattr(cli_main, 'init_retrieve_context_tool', lambda: None)
    fake_gui = MagicMock()
    monkeypatch.setitem(__import__('sys').modules, 'devteam.gui', fake_gui)
    cli_main.main_ui()
    fake_gui.run_server.assert_called_once()


# =====================================================================
# runtime
# =====================================================================

class TestRuntime:
    def test_resolve_thread_id_resume(self):
        req = ResumeRequest(provider='ollama', resume_thread='t99')
        assert runtime.resolve_thread_id(req) == 't99'

    def test_resolve_thread_id_start(self):
        req = StartRequest(provider='ollama', project_name='My App', requirements='r')
        tid = runtime.resolve_thread_id(req)
        assert tid.startswith('my_app_')

    def test_run_executes_crew(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        fake_crew = MagicMock()
        fake_crew.execute = AsyncMock(return_value='RESULT')
        fake_factory = MagicMock()
        fake_factory.create.return_value = fake_crew
        monkeypatch.setattr(runtime, 'CrewFactory', lambda **k: fake_factory)
        monkeypatch.setattr(runtime, 'LLMFactory', lambda **k: MagicMock())

        req = StartRequest(provider='ollama', project_name='App', requirements='build')
        result = asyncio.run(runtime.run(req, 'thread1'))
        assert result == 'RESULT'
        fake_crew.execute.assert_awaited_once()

    def test_run_resume_passes_feedback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        fake_crew = MagicMock()
        fake_crew.execute = AsyncMock(return_value='R')
        fake_factory = MagicMock()
        fake_factory.create.return_value = fake_crew
        monkeypatch.setattr(runtime, 'CrewFactory', lambda **k: fake_factory)
        monkeypatch.setattr(runtime, 'LLMFactory', lambda **k: MagicMock())

        req = ResumeRequest(provider='ollama', resume_thread='thread1', feedback='fix', workflow='development-fanout')
        asyncio.run(runtime.run(req, 'thread1'))
        _, kwargs = fake_crew.execute.call_args
        assert kwargs['feedback'] == 'fix'

    def test_run_seeds_workspace(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        seed = tmp_path / 'seed'
        seed.mkdir()
        (seed / 'a.py').write_text('x', encoding='utf-8')
        fake_crew = MagicMock()
        fake_crew.execute = AsyncMock(return_value='R')
        fake_factory = MagicMock()
        fake_factory.create.return_value = fake_crew
        monkeypatch.setattr(runtime, 'CrewFactory', lambda **k: fake_factory)
        monkeypatch.setattr(runtime, 'LLMFactory', lambda **k: MagicMock())
        hydrated = {}
        monkeypatch.setattr(runtime, 'hydrate_workspace', lambda s, d: hydrated.setdefault('seed', s))

        req = StartRequest(provider='ollama', project_name='App', requirements='r', seed_path=str(seed))
        asyncio.run(runtime.run(req, 'thread1'))
        assert hydrated['seed'] == str(seed)

    def test_async_main_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        monkeypatch.setattr(runtime, 'add_file_handler', lambda p: MagicMock())
        monkeypatch.setattr(runtime, 'remove_file_handler', lambda h: None)
        final = MagicMock()
        final.abort_requested = False
        final.failed_tasks = []
        final.success = True
        final.final_report = 'Report!'
        async def fake_run(req, tid, hooks):
            return final
        monkeypatch.setattr(runtime, 'run', fake_run)
        req = StartRequest(provider='ollama', project_name='App', requirements='r')
        asyncio.run(runtime.async_main(req))

    def test_async_main_aborted(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        monkeypatch.setattr(runtime, 'add_file_handler', lambda p: MagicMock())
        monkeypatch.setattr(runtime, 'remove_file_handler', lambda h: None)
        final = MagicMock()
        final.abort_requested = True
        async def fake_run(req, tid, hooks):
            return final
        monkeypatch.setattr(runtime, 'run', fake_run)
        req = ResumeRequest(provider='ollama', resume_thread='thread1')
        asyncio.run(runtime.async_main(req))

    def test_async_main_release_failed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        monkeypatch.setattr(runtime, 'add_file_handler', lambda p: MagicMock())
        monkeypatch.setattr(runtime, 'remove_file_handler', lambda h: None)
        final = MagicMock()
        final.abort_requested = False
        final.failed_tasks = ['T1']
        final.success = False
        final.integration_bugs = ['bug1']
        async def fake_run(req, tid, hooks):
            return final
        monkeypatch.setattr(runtime, 'run', fake_run)
        req = StartRequest(provider='ollama', project_name='App', requirements='r')
        asyncio.run(runtime.async_main(req))

    def test_async_main_keyboard_interrupt(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        monkeypatch.setattr(runtime, 'add_file_handler', lambda p: MagicMock())
        monkeypatch.setattr(runtime, 'remove_file_handler', lambda h: None)
        async def fake_run(req, tid, hooks):
            raise KeyboardInterrupt()
        monkeypatch.setattr(runtime, 'run', fake_run)
        req = StartRequest(provider='ollama', project_name='App', requirements='r')
        asyncio.run(runtime.async_main(req))  # should be swallowed

    def test_show_history(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        fake_crew = MagicMock()
        fake_crew.get_history = AsyncMock(return_value=[
            {'time': '2026', 'c_id': 'c1', 'node': 'pm'}])
        fake_factory = MagicMock()
        fake_factory.create.return_value = fake_crew
        monkeypatch.setattr(runtime, 'CrewFactory', lambda **k: fake_factory)
        monkeypatch.setattr(runtime, 'LLMFactory', lambda **k: MagicMock())
        asyncio.run(runtime.show_history('thread1'))
        fake_crew.get_history.assert_awaited_once()


# =====================================================================
# cli/extensions
# =====================================================================

class TestBuildExtensions:
    def test_includes_hitl_always(self, monkeypatch):
        monkeypatch.setattr(settings, 'console', False)
        exts = build_extensions()
        names = {type(e).__name__ for e in exts}
        assert 'HumanInTheLoop' in names
        assert 'ConsoleLogger' not in names

    def test_includes_console_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, 'console', True)
        exts = build_extensions()
        names = {type(e).__name__ for e in exts}
        assert 'ConsoleLogger' in names
