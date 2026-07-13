import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import HumanMessage
from devteam.gui import app as gui_app
from devteam.gui.app import (
    ProjectContext, _serialize_event, _serialize_state, _msg_to_dict,
    get_providers_from_config, create_app,
)


@pytest.fixture
def gui_dist(tmp_path):
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html>app</html>', encoding='utf-8')
    (dist / 'main.js').write_text('console.log(1)', encoding='utf-8')
    return dist


@pytest.fixture
def client(gui_dist, monkeypatch):
    monkeypatch.setattr(gui_app, '_projects', {})
    app = create_app(gui_dist)
    app.config.update(TESTING=True)
    return app.test_client()


# =====================================================================
# helper functions
# =====================================================================

class TestSerialization:
    def test_msg_to_dict(self):
        d = _msg_to_dict(HumanMessage(content='hello'))
        assert d == {'type': 'HumanMessage', 'content': 'hello'}

    def test_msg_to_dict_handles_error(self):
        bad = MagicMock()
        type(bad).content = property(lambda self: (_ for _ in ()).throw(ValueError()))
        d = _msg_to_dict(bad)
        assert d['type'] == 'unknown'

    def test_serialize_state_non_dict(self):
        assert _serialize_state("not a dict") == {}

    def test_serialize_state_handles_types(self, tmp_path):
        state = {
            'requirements': 'r',
            'count': 3,
            'flag': True,
            'messages': [HumanMessage(content='hi')],
            'a_list': [1, 'two', object()],
            'a_dict': {'k': object(), 'n': 5},
            'obj': object(),
        }
        out = _serialize_state(state)
        assert out['requirements'] == 'r'
        assert out['messages'][0]['content'] == 'hi'
        assert isinstance(out['a_list'][2], str)
        assert isinstance(out['a_dict']['k'], str)

    def test_serialize_state_reads_workspace_files(self, workspace_dir):
        out = _serialize_state({'workspace_path': workspace_dir})
        assert 'workspace_files' in out
        assert any('main.py' in p for p in out['workspace_files'])

    def test_serialize_event(self):
        event = {'type': 'step', 'ts': 1.0, 'full_state': {'requirements': 'r'},
                 'other': object()}
        out = _serialize_event(event)
        assert out['type'] == 'step'
        assert out['full_state']['requirements'] == 'r'
        assert isinstance(out['other'], str)


class TestProjectContext:
    def test_drain_and_snapshot(self):
        q = Queue()
        q.put({'a': 1})
        q.put({'b': 2})
        ctx = ProjectContext('t', q, None, {}, MagicMock())
        ctx.drain_queue()
        snap = ctx.snapshot()
        assert len(snap) == 2


class TestProviders:
    def test_get_providers_from_config(self):
        providers = get_providers_from_config()
        assert 'ollama' in providers

    def test_get_providers_fallback_missing(self, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'tools_config_dir', tmp_path / 'missing')
        providers = get_providers_from_config()
        assert 'ollama' in providers  # hardcoded fallback


# =====================================================================
# Flask routes
# =====================================================================

class TestRoutes:
    def test_serve_react_index(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'app' in resp.data

    def test_serve_react_static_file(self, client):
        resp = client.get('/main.js')
        assert resp.status_code == 200

    def test_serve_react_unknown_path_returns_index(self, client):
        resp = client.get('/some/spa/route')
        assert resp.status_code == 200
        assert b'app' in resp.data

    def test_api_providers(self, client):
        resp = client.get('/api/providers')
        assert resp.status_code == 200
        assert 'ollama' in resp.get_json()

    def test_api_threads_empty(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path / 'no_ws')
        resp = client.get('/api/threads')
        assert resp.get_json() == []

    def test_api_threads_lists(self, client, monkeypatch, tmp_path):
        from devteam import settings
        ws = tmp_path / 'ws'
        ws.mkdir()
        monkeypatch.setattr(settings, 'workspace_dir', ws)
        (ws / 'thread_a').mkdir()
        (ws / 'thread_b').mkdir()
        resp = client.get('/api/threads')
        assert set(resp.get_json()) == {'thread_a', 'thread_b'}

    def test_api_start_project_requires_requirements(self, client):
        resp = client.post('/api/projects', json={'requirements': '  '})
        assert resp.status_code == 400

    def test_api_start_project_launches_worker(self, client, monkeypatch):
        monkeypatch.setattr(gui_app.threading, 'Thread', lambda *a, **k: MagicMock())
        resp = client.post('/api/projects', json={
            'requirements': 'Build a calculator', 'provider': 'ollama', 'ask_all': True})
        assert resp.status_code == 200
        assert 'thread_id' in resp.get_json()

    def test_api_resume_thread_not_found(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        resp = client.post('/api/projects/ghost/resume', json={})
        assert resp.status_code == 404

    def test_api_resume_launches(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        monkeypatch.setattr(gui_app.threading, 'Thread', lambda *a, **k: MagicMock())
        resp = client.post('/api/projects/thread1/resume', json={'feedback': 'fix'})
        assert resp.status_code == 200

    def test_api_hitl_no_project(self, client):
        resp = client.post('/api/projects/ghost/hitl', json={'response': 'hi'})
        assert resp.status_code == 404

    def test_api_hitl_submit_response(self, client):
        hitl = MagicMock()
        ctx = ProjectContext('t1', Queue(), hitl, {}, MagicMock())
        gui_app._register_project(ctx)
        resp = client.post('/api/projects/t1/hitl', json={'response': 'use a dict'})
        assert resp.status_code == 200
        hitl.submit_response.assert_called_once_with('use a dict')

    def test_api_hitl_abort(self, client):
        hitl = MagicMock()
        ctx = ProjectContext('t2', Queue(), hitl, {}, MagicMock())
        gui_app._register_project(ctx)
        resp = client.post('/api/projects/t2/hitl', json={'abort': True})
        assert resp.status_code == 200
        hitl.abort.assert_called_once()

    def test_api_history_not_found(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        resp = client.get('/api/projects/ghost/history')
        assert resp.status_code == 404

    def test_api_history_success(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        monkeypatch.setattr(gui_app, '_fetch_history', lambda tid: [{'c_id': 'c1'}])
        resp = client.get('/api/projects/thread1/history')
        assert resp.status_code == 200
        assert resp.get_json()[0]['c_id'] == 'c1'

    def test_api_history_error(self, client, monkeypatch, tmp_path):
        from devteam import settings
        monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
        (tmp_path / 'thread1').mkdir()
        def boom(tid):
            raise RuntimeError("db error")
        monkeypatch.setattr(gui_app, '_fetch_history', boom)
        resp = client.get('/api/projects/thread1/history')
        assert resp.status_code == 500

    def test_api_state_not_found(self, client):
        resp = client.get('/api/projects/ghost/state')
        assert resp.status_code == 404

    def test_api_state_returns_full_state(self, client):
        q = Queue()
        q.put({'full_state': {'requirements': 'r'}})
        worker = MagicMock()
        worker.is_alive.return_value = False
        ctx = ProjectContext('t3', q, None, {'final_state': 'done'}, worker)
        gui_app._register_project(ctx)
        resp = client.get('/api/projects/t3/state')
        body = resp.get_json()
        assert body['full_state'] == {'requirements': 'r'}
        assert body['running'] is False

    def test_api_stream_not_found(self, client):
        resp = client.get('/api/projects/ghost/stream')
        assert resp.status_code == 404

    def test_api_stream_emits_done(self, client):
        q = Queue()
        q.put({'type': 'step', 'ts': 1.0})
        worker = MagicMock()
        worker.is_alive.return_value = False
        ctx = ProjectContext('t4', q, None, {}, worker)
        gui_app._register_project(ctx)
        resp = client.get('/api/projects/t4/stream')
        data = resp.get_data(as_text=True)
        assert '__done__' in data


# =====================================================================
# _run_in_thread / _fetch_history (worker-side helpers)
# =====================================================================

def test_run_in_thread_success(monkeypatch, tmp_path):
    from devteam import settings
    monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
    monkeypatch.setattr(gui_app, 'add_file_handler', lambda p: MagicMock())
    monkeypatch.setattr(gui_app, 'remove_file_handler', lambda h: None)

    async def fake_run(request, thread_id, hooks):
        return 'FINAL'
    monkeypatch.setattr(gui_app, 'run', fake_run)

    from devteam.cli.request import StartRequest
    req = StartRequest(provider='ollama', project_name='App', requirements='r')
    holder = {}
    gui_app._run_in_thread(req, 'thread1', Queue(), holder)
    assert holder['final_state'] == 'FINAL'


def test_run_in_thread_failure(monkeypatch, tmp_path):
    from devteam import settings
    monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
    monkeypatch.setattr(gui_app, 'add_file_handler', lambda p: MagicMock())
    monkeypatch.setattr(gui_app, 'remove_file_handler', lambda h: None)

    async def fake_run(request, thread_id, hooks):
        raise RuntimeError("worker boom")
    monkeypatch.setattr(gui_app, 'run', fake_run)

    from devteam.cli.request import StartRequest
    req = StartRequest(provider='ollama', project_name='App', requirements='r')
    holder = {}
    q = Queue()
    gui_app._run_in_thread(req, 'thread1', q, holder)
    assert 'worker boom' in holder['error']
    assert q.get_nowait()['type'] == 'error'


def test_run_in_thread_emits_telemetry_event(monkeypatch, tmp_path):
    from devteam import settings
    from devteam.utils import TelemetryTracker
    monkeypatch.setattr(settings, 'workspace_dir', tmp_path)
    monkeypatch.setattr(gui_app, 'add_file_handler', lambda p: MagicMock())
    monkeypatch.setattr(gui_app, 'remove_file_handler', lambda h: None)

    async def fake_run(request, thread_id, hooks):
        tracker = hooks.callbacks[0]
        assert isinstance(tracker, TelemetryTracker)
        # Simulate one LLM call so the finally-block emits a telemetry event
        tracker.total_requests = 1
        tracker.input_tokens = 100
        tracker.output_tokens = 50
        return 'FINAL'
    monkeypatch.setattr(gui_app, 'run', fake_run)

    from devteam.cli.request import StartRequest
    req = StartRequest(provider='ollama', project_name='App', requirements='r')
    q = Queue()
    gui_app._run_in_thread(req, 'thread1', q, {})
    event = q.get_nowait()
    assert event['type'] == 'telemetry'
    assert event['total_requests'] == 1
    assert event['total_tokens'] == 150
    assert event['diagnostics'] == []
