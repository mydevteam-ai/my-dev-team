import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from devteam.state import ProjectState

@pytest.fixture(autouse=True)
def _isolate_run_log(tmp_path):
    """Keep the persistent run log out of the real ~/.devteam during tests.

    Patched by hand rather than via the monkeypatch fixture: requesting
    monkeypatch here would reorder its teardown after module-local autouse
    fixtures that undo their own patches in teardown.
    """
    from devteam.utils import run_log
    original = run_log.default_run_log_path
    run_log.default_run_log_path = lambda: tmp_path / 'run-log.jsonl'
    yield
    run_log.default_run_log_path = original


@pytest.fixture
def sample_state():
    return ProjectState(requirements='Build a REST API')

@pytest.fixture
def sample_workspace_files():
    return {
        'src/main.py': 'print("hello")',
        'tests/test_main.py': 'def test_main(): pass',
    }

@pytest.fixture
def workspace_dir(tmp_path, sample_workspace_files):
    """Materialize sample_workspace_files on disk and return the str path."""
    for rel, content in sample_workspace_files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    return str(tmp_path)

@pytest.fixture
def sample_task():
    return {
        'task_name': 'Create User Model',
        'user_story': 'As a developer, I want a User model.',
        'acceptance_criteria': ['User has name', 'User has email'],
    }

@pytest.fixture
def mock_llm_factory():
    factory = MagicMock()
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"specs": "test specs"}'))
    factory.create.return_value = mock_llm
    return factory
