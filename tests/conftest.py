import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from devteam.state import ProjectState

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
