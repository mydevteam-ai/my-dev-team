import subprocess
from typing import override
from pathlib import Path
from .base_extension import CrewExtension

class GitCommitter(CrewExtension):
    """Extension that commits workspace changes to a Git repository."""

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
            self._run_git('init')
            self._run_git('config', 'user.name', 'DevTeam')
            self._run_git('config', 'user.email', 'devteam@local')

    def _commit(self, message: str):
        self._run_git('add', '-A')
        status = self._run_git('status', '--porcelain')
        if status.stdout.strip():
            self._run_git('commit', '-m', message)

    @override
    def on_start(self, thread_id: str, initial_state: dict):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self._init_repo()
        self._commit('Initial commit')

    @override
    def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        for node_name, node_update in state_update.items():
            if node_name != 'developer':
                continue
            if not isinstance(node_update, dict):
                continue
            workspace_files = node_update.get('workspace_files', {})
            if not workspace_files:
                continue
            revision = node_update.get('revision_count', 0)
            task_index = full_state.get('current_task_index', 0)
            message = f"Task {task_index} - revision {revision}"
            self._commit(message)
