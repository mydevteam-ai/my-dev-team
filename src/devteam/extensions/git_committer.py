import asyncio
import subprocess
from typing import override
from pathlib import Path
from .base_extension import CrewExtension

class GitCommitter(CrewExtension):
    """Extension that commits workspace changes to a Git repository."""

    critical = True

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ['git', *args],
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

    def _init_repo(self):
        if not (self.workspace_dir / '.git').exists():
            result = self._run_git('init')
            if result.returncode != 0:
                self.logger.warning("git init failed: %s", result.stderr.strip())
                return
            self._run_git('config', 'user.name', 'DevTeam')
            self._run_git('config', 'user.email', 'devteam@local')

    def _commit(self, message: str):
        result = self._run_git('add', '-A')
        if result.returncode != 0:
            self.logger.warning("git add failed: %s", result.stderr.strip())
            return
        result = self._run_git('status', '--porcelain')
        if result.stdout.strip():
            result = self._run_git('commit', '-m', message)
            if result.returncode != 0:
                self.logger.warning("git commit failed: %s", result.stderr.strip())

    def _sync_on_start(self, thread_id: str, initial_state: dict):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self._init_repo()
        self._commit('Initial commit')

    def _sync_on_step(self, thread_id: str, state_update: dict, full_state: dict):
        for node_name, node_update in state_update.items():
            if node_name != 'developer':
                continue
            if not isinstance(node_update, dict):
                continue
            workspace_files = node_update.get('workspace_files', {})
            if not workspace_files:
                continue
            revision = node_update.get('revision_count', 0)
            task_index = len(full_state.get('completed_tasks', [])) + 1
            message = f"Task {task_index} - revision {revision}"
            self._commit(message)

    @override
    async def on_start(self, thread_id: str, initial_state: dict):
        await asyncio.to_thread(self._sync_on_start, thread_id, initial_state)

    @override
    async def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        await asyncio.to_thread(self._sync_on_step, thread_id, state_update, full_state)
