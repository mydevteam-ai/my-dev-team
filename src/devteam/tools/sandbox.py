from functools import cached_property
from pathlib import Path
import docker
from docker.errors import ImageNotFound
import yaml
from devteam import settings
from devteam.utils import WithLogging

class DockerSandbox(WithLogging):
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e: # pylint: disable=broad-exception-caught
            raise RuntimeError(f"Could not connect to Docker. Error: {e}") from e

    @cached_property
    def _sandbox_config(self) -> dict:
        config_path = settings.config_dir / 'sandbox.yaml'
        return yaml.safe_load(config_path.read_text(encoding='utf-8'))

    @cached_property
    def _runtimes(self) -> dict:
        return self._sandbox_config.get('runtimes', {})

    def _pull_image(self, image: str):
        try:
            self.client.images.get(image)
        except ImageNotFound:
            self.logger.info("Pulling %s (this only happens once)...", image)
            self.client.images.pull(image)

    def run_tests(self, workspace_dir: Path, runtime: str = 'python', timeout: int = 15) -> str:
        absolute_workspace = workspace_dir.resolve()
        config = self._runtimes.get(runtime.lower())
        if not config:
            return f"⚠️ Sandbox Error: Unsupported runtime '{runtime}'. Supported runtimes: {list(self._runtimes.keys())}"
        self._pull_image(config['image'])
        container = None
        try:
            container = self.client.containers.run(
                image=config['image'],
                command=config['command'],
                volumes={str(absolute_workspace): {'bind': '/workspace', 'mode': 'rw'}},
                working_dir='/workspace',
                network_disabled=True,
                mem_limit=config.get('mem_limit', '256m'),
                nano_cpus=1_000_000_000,
                detach=True
            )
            result = container.wait(timeout=timeout)
            exit_code = result['StatusCode']
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            if exit_code == 0:
                return f"✅ Tests Passed:\n{logs}"
            else:
                return f"❌ Tests Failed (Exit Code {exit_code}):\n{logs}"
        except Exception as e: # pylint: disable=broad-exception-caught
            return f"⚠️ Sandbox Execution Error: {str(e)}"
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception: # pylint: disable=broad-exception-caught
                    self.logger.warning("Failed to remove container %s", container.id)
