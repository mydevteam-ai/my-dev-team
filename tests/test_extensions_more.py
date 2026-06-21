import asyncio
import threading
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch
import pytest
from devteam import settings
from devteam.extensions.console_logger import ConsoleLogger
from devteam.extensions.hitl_cli import HumanInTheLoop
from devteam.extensions.hitl_gui import HumanInTheLoopGUI
from devteam.extensions.streamlit_logger import StreamlitLogger
from devteam.extensions.git_committer import GitCommitter
from devteam.extensions.workspace_saver import WorkspaceSaver
from devteam.state import TaskContext


@pytest.fixture(autouse=True)
def _reset_flags():
    saved = (settings.ask_approval, settings.ask_all)
    settings.ask_approval = False
    settings.ask_all = False
    yield
    settings.ask_approval, settings.ask_all = saved


# =====================================================================
# ConsoleLogger lifecycle hooks
# =====================================================================

class TestConsoleLogger:
    def _logger(self, monkeypatch):
        logger = ConsoleLogger()
        printed = []
        monkeypatch.setattr('devteam.extensions.console_logger.print', lambda *a, **k: printed.append(a))
        return logger, printed

    def test_on_start_planning(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_start('t', {'requirements': 'build'}))
        assert printed

    def test_on_start_execution(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_start('t', {'current_task': 'do it'}))
        assert printed

    def test_on_start_release(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_start('t', {'code': 'x', 'final_report': 'r'}))
        assert printed

    def test_on_resume(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_resume('t', {'review_feedback': 'fix'}))
        assert printed

    def test_on_finish_with_tasks(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_finish('t', {'pending_tasks': [{'task_name': 'A'}]}))
        assert printed

    def test_on_finish_with_code(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_finish('t', {'code': 'x', 'revision_count': 2}))
        assert printed

    def test_on_finish_with_report(self, monkeypatch):
        logger, printed = self._logger(monkeypatch)
        asyncio.run(logger.on_finish('t', {'final_report': 'done'}))
        assert printed


# =====================================================================
# HumanInTheLoop (CLI)
# =====================================================================

class TestHitlCli:
    def test_on_step_tracks_last_agent(self):
        ext = HumanInTheLoop()
        asyncio.run(ext.on_step('t', {'developer': {}}, {}))
        assert ext._last_agent == 'developer'

    def test_on_step_ignores_system_nodes(self):
        ext = HumanInTheLoop()
        ext._last_agent = 'developer'
        asyncio.run(ext.on_step('t', {'manager': {}}, {}))
        assert ext._last_agent == 'developer'

    def test_clarification_abort(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'exit')
        update = asyncio.run(ext.on_pause('t', {'clarification_question': 'q?'}, 'human'))
        assert update['abort_requested'] is True

    def test_spec_approval_approved(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'approved')
        update = asyncio.run(ext.on_pause('t', {'specs': 'the spec'}, 'human'))
        assert update['specs_approved'] is True

    def test_spec_approval_rework(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'add more detail')
        update = asyncio.run(ext.on_pause('t', {'specs': 'the spec'}, 'human'))
        assert update['specs_approved'] is False
        assert update['specs'] == ''

    def test_spec_approval_abort(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'quit')
        update = asyncio.run(ext.on_pause('t', {'specs': 'the spec'}, 'human'))
        assert update['abort_requested'] is True

    def test_task_plan_approval_approved(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'approved')
        state = {'specs': 's', 'pending_tasks': [
            {'task_name': 'A', 'user_story': 'story', 'dependencies': []},
        ]}
        update = asyncio.run(ext.on_pause('t', state, 'human'))
        assert update['tasks_approved'] is True
        assert update['current_phase'] == 'development'

    def test_task_plan_approval_rework(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'reorder tasks')
        state = {'specs': 's', 'pending_tasks': [
            {'task_name': 'A', 'user_story': 'story', 'dependencies': ['X']},
        ]}
        update = asyncio.run(ext.on_pause('t', state, 'human'))
        assert update['pending_tasks'] == []

    def test_task_plan_approval_abort(self, monkeypatch):
        ext = HumanInTheLoop()
        monkeypatch.setattr('builtins.input', lambda _: 'exit')
        state = {'specs': 's', 'pending_tasks': [
            {'task_name': 'A', 'user_story': 'story', 'dependencies': []},
        ]}
        update = asyncio.run(ext.on_pause('t', state, 'human'))
        assert update['abort_requested'] is True

    def test_agent_approval_continue(self, monkeypatch):
        settings.ask_all = True
        ext = HumanInTheLoop()
        ext._last_agent = 'developer'
        monkeypatch.setattr('builtins.input', lambda _: '')
        update = asyncio.run(ext.on_pause('t', {'task_context': TaskContext()}, 'manager'))
        assert 'Approved' in update['communication_log'][0]

    def test_agent_approval_abort(self, monkeypatch):
        settings.ask_all = True
        ext = HumanInTheLoop()
        ext._last_agent = 'developer'
        monkeypatch.setattr('builtins.input', lambda _: 'exit')
        update = asyncio.run(ext.on_pause('t', {}, 'manager'))
        assert update['abort_requested'] is True

    def test_agent_approval_feedback_to_developer(self, monkeypatch):
        settings.ask_all = True
        ext = HumanInTheLoop()
        ext._last_agent = 'developer'
        monkeypatch.setattr('builtins.input', lambda _: 'use a dict instead')
        state = {'task_context': TaskContext(current_task_name='A')}
        update = asyncio.run(ext.on_pause('t', state, 'manager'))
        assert update['task_context'].human_feedback == 'use a dict instead'

    def test_build_feedback_update_pm(self):
        ext = HumanInTheLoop()
        update = ext._build_feedback_update('pm', 'redo spec', {})
        assert update['specs'] == ''
        assert update['specs_approved'] is False

    def test_build_feedback_update_architect(self):
        ext = HumanInTheLoop()
        update = ext._build_feedback_update('architect', 'redo plan', {})
        assert update['pending_tasks'] == []
        assert update['tasks_approved'] is False

    def test_build_feedback_update_other_agent(self):
        ext = HumanInTheLoop()
        update = ext._build_feedback_update('reporter', 'note', {})
        assert 'Note after reporter' in update['communication_log'][0]

    def test_build_feedback_update_dev_without_task_context(self):
        ext = HumanInTheLoop()
        update = ext._build_feedback_update('developer', 'fix', {})
        # No task_context -> falls through to default note.
        assert 'Note after developer' in update['communication_log'][0]


# =====================================================================
# HumanInTheLoopGUI
# =====================================================================

class TestHitlGui:
    def _run_with_response(self, ext, coro_factory, response=None, abort=False):
        def respond():
            if abort:
                ext.abort()
            else:
                ext.submit_response(response)
        timer = threading.Timer(0.05, respond)
        timer.start()
        try:
            return asyncio.run(coro_factory())
        finally:
            timer.cancel()

    def test_on_step_tracks_agent(self):
        ext = HumanInTheLoopGUI(Queue())
        asyncio.run(ext.on_step('t', {'reviewer': {}}, {}))
        assert ext._last_agent == 'reviewer'

    def test_on_pause_non_human_returns_none(self):
        ext = HumanInTheLoopGUI(Queue())
        assert asyncio.run(ext.on_pause('t', {}, 'developer')) is None

    def test_clarification_abort(self):
        ext = HumanInTheLoopGUI(Queue())
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', {'clarification_question': 'q'}, 'human'),
            abort=True)
        assert update['abort_requested'] is True

    def test_spec_approval_approved(self):
        q = Queue()
        ext = HumanInTheLoopGUI(q)
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', {'specs': 'spec'}, 'human'),
            response='approved')
        assert update['specs_approved'] is True
        assert q.get(timeout=1)['mode'] == 'approval_spec'

    def test_spec_approval_rework(self):
        ext = HumanInTheLoopGUI(Queue())
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', {'specs': 'spec'}, 'human'),
            response='needs work')
        assert update['specs'] == ''

    def test_task_plan_approval_approved(self):
        q = Queue()
        ext = HumanInTheLoopGUI(q)
        state = {'specs': 's', 'pending_tasks': [{'task_name': 'A'}]}
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', state, 'human'), response='approved')
        assert update['tasks_approved'] is True
        assert q.get(timeout=1)['mode'] == 'approval_plan'

    def test_task_plan_rework(self):
        ext = HumanInTheLoopGUI(Queue())
        state = {'specs': 's', 'pending_tasks': [{'task_name': 'A'}]}
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', state, 'human'), response='redo')
        assert update['pending_tasks'] == []

    def test_agent_approval_approved(self):
        settings.ask_all = True
        ext = HumanInTheLoopGUI(Queue())
        ext._last_agent = 'developer'
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', {'task_context': TaskContext()}, 'manager'),
            response='approved')
        assert 'Approved' in update['communication_log'][0]

    def test_agent_approval_abort(self):
        settings.ask_all = True
        ext = HumanInTheLoopGUI(Queue())
        ext._last_agent = 'developer'
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', {}, 'manager'), abort=True)
        assert update['abort_requested'] is True

    def test_agent_approval_feedback(self):
        settings.ask_all = True
        ext = HumanInTheLoopGUI(Queue())
        ext._last_agent = 'developer'
        state = {'task_context': TaskContext(current_task_name='A')}
        update = self._run_with_response(
            ext, lambda: ext.on_pause('t', state, 'manager'), response='use list')
        assert update['task_context'].human_feedback == 'use list'

    def test_build_feedback_update_pm(self):
        ext = HumanInTheLoopGUI(Queue())
        update = ext._build_feedback_update('pm', 'redo', {})
        assert update['specs_approved'] is False

    def test_build_feedback_update_analyzer(self):
        ext = HumanInTheLoopGUI(Queue())
        update = ext._build_feedback_update('analyzer', 'redo', {})
        assert update['tasks_approved'] is False


# =====================================================================
# StreamlitLogger
# =====================================================================

class TestStreamlitLogger:
    def test_on_start_emits(self):
        q = Queue()
        StreamlitLogger(q)
        ext = StreamlitLogger(q)
        asyncio.run(ext.on_start('t', {'requirements': 'r'}))
        assert q.get_nowait()['type'] == 'start'

    def test_on_resume_emits(self):
        q = Queue()
        ext = StreamlitLogger(q)
        asyncio.run(ext.on_resume('t', {'x': 1}))
        assert q.get_nowait()['type'] == 'resume'

    def test_on_step_emits(self):
        q = Queue()
        ext = StreamlitLogger(q)
        asyncio.run(ext.on_step('t', {'pm': {}}, {}))
        assert q.get_nowait()['type'] == 'step'

    def test_on_pause_emits_and_returns_none(self):
        q = Queue()
        ext = StreamlitLogger(q)
        result = asyncio.run(ext.on_pause('t', {}, 'human'))
        assert result is None
        assert q.get_nowait()['type'] == 'pause'

    def test_on_finish_success(self):
        q = Queue()
        ext = StreamlitLogger(q)
        asyncio.run(ext.on_finish('t', {'final_report': 'done'}))
        assert q.get_nowait()['type'] == 'finish'

    def test_on_finish_error(self):
        q = Queue()
        ext = StreamlitLogger(q)
        asyncio.run(ext.on_finish('t', {'error': True}))
        assert q.get_nowait()['type'] == 'error'


# =====================================================================
# GitCommitter
# =====================================================================

class TestGitCommitter:
    def _committer(self, tmp_path):
        return GitCommitter(workspace_dir=tmp_path / 'workspace')

    def test_init_repo_and_commit(self, tmp_path):
        gc = self._committer(tmp_path)
        results = []

        def fake_run(*args):
            results.append(args)
            res = MagicMock()
            res.returncode = 0
            res.stdout = ' M file.py' if args[0] == 'status' else ''
            res.stderr = ''
            return res
        gc._run_git = fake_run
        gc._sync_on_start('t', {})
        assert any(a[0] == 'init' for a in results)
        assert any(a[0] == 'commit' for a in results)

    def test_commit_nothing_to_commit(self, tmp_path):
        gc = self._committer(tmp_path)

        def fake_run(*args):
            res = MagicMock()
            res.returncode = 0
            res.stdout = ''  # clean tree
            res.stderr = ''
            return res
        gc._run_git = fake_run
        # Should not raise even when there's nothing to commit.
        gc._commit('msg')

    def test_commit_add_failure_logged(self, tmp_path):
        gc = self._committer(tmp_path)

        def fake_run(*args):
            res = MagicMock()
            res.returncode = 1 if args[0] == 'add' else 0
            res.stdout = ''
            res.stderr = 'add error'
            return res
        gc._run_git = fake_run
        gc._commit('msg')  # logs warning, returns

    def test_init_repo_skipped_when_git_exists(self, tmp_path):
        ws = tmp_path / 'workspace'
        ws.mkdir(parents=True)
        (ws / '.git').mkdir()
        gc = GitCommitter(workspace_dir=ws)
        calls = []
        gc._run_git = lambda *a: calls.append(a) or MagicMock(returncode=0, stdout='', stderr='')
        gc._init_repo()
        assert not any(a[0] == 'init' for a in calls)

    def test_sync_on_step_commits_developer_changes(self, tmp_path):
        gc = self._committer(tmp_path)
        commits = []
        gc._commit = lambda msg: commits.append(msg)
        tc = TaskContext(developer_drafts={'developer': {'a.py': 'x'}}, revision_count=1)
        gc._sync_on_step('t', {'developer': {'task_context': tc}}, {'completed_tasks': []})
        assert commits and 'revision 1' in commits[0]

    def test_sync_on_step_ignores_non_developer(self, tmp_path):
        gc = self._committer(tmp_path)
        commits = []
        gc._commit = lambda msg: commits.append(msg)
        gc._sync_on_step('t', {'reviewer': {'task_context': TaskContext()}}, {})
        assert commits == []

    def test_sync_on_step_ignores_no_changed_files(self, tmp_path):
        gc = self._committer(tmp_path)
        commits = []
        gc._commit = lambda msg: commits.append(msg)
        gc._sync_on_step('t', {'developer': {'task_context': TaskContext()}}, {})
        assert commits == []

    def test_on_start_and_on_step_async(self, tmp_path):
        gc = self._committer(tmp_path)
        gc._sync_on_start = MagicMock()
        gc._sync_on_step = MagicMock()
        asyncio.run(gc.on_start('t', {}))
        asyncio.run(gc.on_step('t', {}, {}))
        gc._sync_on_start.assert_called_once()
        gc._sync_on_step.assert_called_once()


# =====================================================================
# WorkspaceSaver additional branches (officer, fanout, drafts)
# =====================================================================

class TestWorkspaceSaverMore:
    def test_officer_saves_task_file(self, tmp_path):
        saver = WorkspaceSaver(tmp_path)
        asyncio.run(saver.on_start('t', {'requirements': 'R'}))
        tc = TaskContext(current_agent='developer', current_task_name='Build API')
        full_state = {
            'current_phase': 'development',
            'task_context': tc,
            'pending_tasks': [{'task_name': 'Build API', 'user_story': 'us',
                               'acceptance_criteria': ['c']}],
        }
        asyncio.run(saver.on_step('t', {'officer': {'task_context': tc}}, full_state))
        assert (tmp_path / '01_task' / 'task.md').exists()

    def test_judge_saves_winner(self, tmp_path):
        saver = WorkspaceSaver(tmp_path)
        asyncio.run(saver.on_start('t', {'requirements': 'R'}))
        tc = TaskContext(
            winner_developer='developer_a',
            developer_drafts={'developer_a': {'a.py': 'code'}},
            current_task_index=1, revision_count=0,
        )
        full_state = {'current_phase': 'development', 'task_context': tc}
        asyncio.run(saver.on_step('t', {'judge': {'task_context': tc}}, full_state))
        assert (tmp_path / '01_task' / 'judge_v0.md').read_text(encoding='utf-8') == 'developer_a'

    def test_developer_draft_saved_to_suffix_dir(self, tmp_path):
        saver = WorkspaceSaver(tmp_path)
        asyncio.run(saver.on_start('t', {'requirements': 'R'}))
        tc = TaskContext(
            developer_drafts={'developer_a': {'a.py': 'draft'}},
            current_task_index=1, revision_count=0,
        )
        full_state = {'current_phase': 'development', 'task_context': tc}
        asyncio.run(saver.on_step('t', {'developer_a': {'task_context': tc}}, full_state))
        assert (tmp_path / '01_task' / 'rev_0_a' / 'a.py').read_text(encoding='utf-8') == 'draft'

    def test_save_workspace_skips_absolute_path(self, tmp_path):
        saver = WorkspaceSaver(tmp_path)
        saver._base_dir = tmp_path / 'task'
        saver._base_dir.mkdir()
        abs_path = str(Path(tmp_path / 'evil.py').resolve())
        saver._save_workspace({abs_path: 'x'}, 0)
        # No crash; absolute path skipped from live dir.
        assert not (saver._live_dir / 'evil.py').exists()

    def test_save_workspace_empty_noop(self, tmp_path):
        saver = WorkspaceSaver(tmp_path)
        saver._base_dir = tmp_path
        saver._save_workspace({}, 0)  # returns immediately
