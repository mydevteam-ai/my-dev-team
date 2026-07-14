import json
from types import SimpleNamespace
import pytest
from devteam import settings
from devteam.cli.request import ResumeRequest, StartRequest
from devteam.utils.run_log import RunLog, build_run_record, default_run_log_path, write_run_record


def _make_telemetry(requests=2, cost=0.5):
    return SimpleNamespace(
        total_requests=requests,
        repaired_calls=1,
        input_tokens=1000,
        cached_tokens=100,
        output_tokens=200,
        total_cost=cost,
        call_history=[
            {'agent': 'dev', 'model': 'm', 'input_tokens': 600, 'cached_tokens': 100,
             'output_tokens': 150, 'cost': 0.3, 'iteration': 1, 'context_fill': None, 'repaired': False},
            {'agent': 'qa', 'model': 'm', 'input_tokens': 400, 'cached_tokens': 0,
             'output_tokens': 50, 'cost': 0.2, 'iteration': 1, 'context_fill': 0.8, 'repaired': True},
        ],
    )


def _start_request():
    return StartRequest(provider='groq', workflow='development', fanout=False,
                        project_name='demo', requirements='Build a thing')


# --- RunLog store ---

def test_append_and_read_roundtrip(tmp_path):
    log = RunLog(tmp_path / 'run-log.jsonl')
    log.append({'record': 'run', 'thread_id': 'a'})
    log.append({'record': 'run', 'thread_id': 'b'})
    records = log.read_records()
    assert [r['thread_id'] for r in records] == ['a', 'b']


def test_read_missing_file_returns_empty(tmp_path):
    assert RunLog(tmp_path / 'nope.jsonl').read_records() == []


def test_read_skips_malformed_and_non_dict_lines(tmp_path):
    path = tmp_path / 'run-log.jsonl'
    path.write_text('{"ok": 1}\n{broken\n[1, 2]\n\n{"ok": 2}\n', encoding='utf-8')
    records = RunLog(path).read_records()
    assert [r['ok'] for r in records] == [1, 2]


def test_append_creates_parent_directory(tmp_path):
    log = RunLog(tmp_path / 'deep' / 'run-log.jsonl')
    log.append({'record': 'run'})
    assert len(log.read_records()) == 1


def test_append_never_raises(tmp_path):
    # Target path is a directory: open() fails, but append must swallow it.
    log = RunLog(tmp_path)
    log.append({'record': 'run'})  # no exception


def test_default_path_is_under_devteam_home():
    path = default_run_log_path()
    assert path.name == 'run-log.jsonl'
    assert path.parent.name == '.devteam'


# --- build_run_record ---

def test_build_run_record_start_request():
    record = build_run_record(_make_telemetry(), _start_request(), 'thread-1',
                              'success', duration_s=12.34)
    assert record['record'] == 'run'
    assert record['thread_id'] == 'thread-1'
    assert record['workflow'] == 'development'
    assert record['provider'] == 'groq'
    assert record['resumed'] is False
    assert record['outcome'] == 'success'
    assert record['duration_s'] == 12.3
    assert record['total_requests'] == 2
    assert record['repaired_calls'] == 1
    assert record['input_tokens'] == 1000
    assert record['cached_tokens'] == 100
    assert record['output_tokens'] == 200
    assert record['total_cost'] == 0.5
    assert len(record['calls']) == 2
    assert 'error' not in record
    # The record must be JSON-serializable as stored.
    json.dumps(record)


def test_build_run_record_resume_and_error():
    request = ResumeRequest(provider='ollama', resume_thread='t')
    record = build_run_record(_make_telemetry(), request, 't', 'error',
                              duration_s=1.0, error='x' * 600)
    assert record['resumed'] is True
    assert record['outcome'] == 'error'
    assert len(record['error']) == 500  # capped


# --- write_run_record ---

@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / 'run-log.jsonl'
    monkeypatch.setattr('devteam.utils.run_log.default_run_log_path', lambda: path)
    return path


def test_write_run_record_appends(log_path):
    import time
    write_run_record(_make_telemetry(), _start_request(), 't1', 'success', time.monotonic())
    records = RunLog(log_path).read_records()
    assert len(records) == 1
    assert records[0]['thread_id'] == 't1'
    assert records[0]['duration_s'] >= 0


def test_write_run_record_gated_by_setting(log_path, monkeypatch):
    import time
    monkeypatch.setattr(settings, 'run_log', False)
    write_run_record(_make_telemetry(), _start_request(), 't1', 'success', time.monotonic())
    assert RunLog(log_path).read_records() == []


def test_write_run_record_skips_empty_run(log_path):
    import time
    write_run_record(_make_telemetry(requests=0), _start_request(), 't1', 'error', time.monotonic())
    assert RunLog(log_path).read_records() == []


def test_write_run_record_never_raises(log_path, monkeypatch):
    import time
    monkeypatch.setattr('devteam.utils.run_log.build_run_record',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    write_run_record(_make_telemetry(), _start_request(), 't1', 'success', time.monotonic())
    assert RunLog(log_path).read_records() == []
