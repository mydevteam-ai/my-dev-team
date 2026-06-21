from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from docker.errors import ImageNotFound
from devteam.tools.sandbox import DockerSandbox


@pytest.fixture
def sandbox(monkeypatch):
    """A DockerSandbox with a mocked docker client (no real daemon)."""
    fake_client = MagicMock()
    with patch('devteam.tools.sandbox.docker.from_env', return_value=fake_client):
        sb = DockerSandbox()
    sb.client = fake_client
    # Override runtime config to avoid reading real yaml dependence.
    sb.__dict__['_runtimes'] = {
        'python': {'image': 'python:test', 'command': 'pytest', 'mem_limit': '128m'},
    }
    return sb


def test_init_connection_failure_raises(monkeypatch):
    with patch('devteam.tools.sandbox.docker.from_env', side_effect=Exception("no daemon")):
        with pytest.raises(RuntimeError, match="Could not connect to Docker"):
            DockerSandbox()


def test_runtimes_reads_config():
    fake_client = MagicMock()
    with patch('devteam.tools.sandbox.docker.from_env', return_value=fake_client):
        sb = DockerSandbox()
    assert 'python' in sb._runtimes  # from bundled sandbox.yaml


def test_run_tests_unsupported_runtime(sandbox, tmp_path):
    result = sandbox.run_tests(tmp_path, runtime='cobol')
    assert 'Unsupported runtime' in result


def test_run_tests_passing(sandbox, tmp_path):
    container = MagicMock()
    container.wait.return_value = {'StatusCode': 0}
    container.logs.return_value = b'2 passed'
    sandbox.client.containers.run.return_value = container
    sandbox.client.images.get.return_value = MagicMock()  # image already present

    result = sandbox.run_tests(tmp_path, runtime='python')
    assert 'Tests Passed' in result
    assert '2 passed' in result
    container.remove.assert_called_once()


def test_run_tests_failing(sandbox, tmp_path):
    container = MagicMock()
    container.wait.return_value = {'StatusCode': 1}
    container.logs.return_value = b'1 failed'
    sandbox.client.containers.run.return_value = container
    sandbox.client.images.get.return_value = MagicMock()

    result = sandbox.run_tests(tmp_path, runtime='python')
    assert 'Tests Failed' in result
    assert 'Exit Code 1' in result


def test_run_tests_pulls_missing_image(sandbox, tmp_path):
    container = MagicMock()
    container.wait.return_value = {'StatusCode': 0}
    container.logs.return_value = b'ok'
    sandbox.client.containers.run.return_value = container
    sandbox.client.images.get.side_effect = ImageNotFound("missing")

    sandbox.run_tests(tmp_path, runtime='python')
    sandbox.client.images.pull.assert_called_once_with('python:test')


def test_run_tests_execution_error(sandbox, tmp_path):
    sandbox.client.images.get.return_value = MagicMock()
    sandbox.client.containers.run.side_effect = RuntimeError("container boom")
    result = sandbox.run_tests(tmp_path, runtime='python')
    assert 'Sandbox Execution Error' in result


def test_run_tests_remove_failure_is_logged(sandbox, tmp_path):
    container = MagicMock()
    container.wait.return_value = {'StatusCode': 0}
    container.logs.return_value = b'ok'
    container.remove.side_effect = Exception("cannot remove")
    sandbox.client.containers.run.return_value = container
    sandbox.client.images.get.return_value = MagicMock()
    # Should swallow the removal error.
    result = sandbox.run_tests(tmp_path, runtime='python')
    assert 'Tests Passed' in result
