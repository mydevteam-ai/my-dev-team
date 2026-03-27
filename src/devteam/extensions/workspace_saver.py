from typing import override
from functools import cached_property
from pathlib import Path
from devteam.utils import task_to_markdown
from .base_extension import CrewExtension

class WorkspaceSaver(CrewExtension):
    _base_dir: Path

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @cached_property
    def _live_dir(self) -> Path:
        return self.workspace_dir / 'workspace'

    @override
    def on_start(self, thread_id: str, initial_state: dict):
        self._base_dir = self._get_target_dir(initial_state)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        initial_state['workspace_path'] = str(self._live_dir)
        if requirements := initial_state.get('requirements'):
            self._save_requirements(requirements)

    def _get_target_dir(self, full_state: dict) -> Path:
        match full_state.get('current_phase', 'planning'):
            case 'integration' | 'complete':
                return self.workspace_dir / '90_integration'
            case 'development':
                task_idx = full_state.get('current_task_index', 1)
                return self.workspace_dir / f'{task_idx:02d}_task'
        return self.workspace_dir / '00_planning'

    def _save_requirements(self, requirements: str):
        requirements_file = self._base_dir / 'requirements.md'
        requirements_file.write_text(requirements, encoding='utf-8')

    def _save_specs(self, specs: str):
        specs_file = self._base_dir / 'specs.md'
        specs_file.write_text(specs, encoding='utf-8')

    def _save_tasks(self, tasks: list):
        tasks_file = self._base_dir / 'tasks.md'
        content = ["# System Execution Plan\n"]
        for idx, task in enumerate(tasks, start=1):
            content.append(task_to_markdown(task, idx))
        tasks_file.write_text('\n'.join(content), encoding='utf-8')

    def _save_current_task(self, current_task: str):
        task_file = self._base_dir / 'task.md'
        task_file.write_text(current_task, encoding='utf-8')

    def _save_workspace(self, workspace_files: dict, current_rev: int):
        if not workspace_files:
            return
        revision_dir = f'rev_{current_rev}'
        self._live_dir.mkdir(parents=True, exist_ok=True)
        for filepath, content in workspace_files.items():
            relative_path = Path(filepath)
            if relative_path.is_absolute():
                self.logger.warning("Skipping absolute path from agent output: %s", filepath)
                continue
            revision_root = (self._base_dir / revision_dir).resolve()
            full_file_path = (revision_root / relative_path).resolve()
            if not full_file_path.is_relative_to(revision_root):
                self.logger.warning("Skipping unsafe workspace path (revision): %s", filepath)
                continue
            full_file_path.parent.mkdir(parents=True, exist_ok=True)
            full_file_path.write_text(content, encoding='utf-8')
            live_root = self._live_dir.resolve()
            live_file_path = (live_root / relative_path).resolve()
            if not live_file_path.is_relative_to(live_root):
                self.logger.warning("Skipping unsafe workspace path (live): %s", filepath)
                continue
            live_file_path.parent.mkdir(parents=True, exist_ok=True)
            live_file_path.write_text(content, encoding='utf-8')

    def _save_code_review(self, review_feedback: str, current_rev: int):
        feedback_file = self._base_dir / f'feedback_v{current_rev}.md'
        feedback_file.write_text(review_feedback, encoding='utf-8')

    def _save_test_results(self, test_results: str, current_rev: int):
        results_file = self._base_dir / f'test_results_v{current_rev}.md'
        results_file.write_text(test_results, encoding='utf-8')

    def _save_final_report(self, report: str):
        report_file = self._base_dir / 'final_report.md'
        report_file.write_text(report, encoding='utf-8')

    @override
    def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        for node_name, node_update in state_update.items():
            self._base_dir = self._get_target_dir(full_state)
            self._base_dir.mkdir(parents=True, exist_ok=True)
            match node_name:
                case 'pm':
                    if specs := node_update.get('specs', ''):
                        self._save_specs(specs)
                case 'architect':
                    if pending := node_update.get('pending_tasks', []):
                        self._save_tasks(pending)
                case 'officer':
                    if node_update.get('current_agent') == 'developer' and node_update.get('revision_count', 0) == 0:
                        if current_task := full_state.get('current_task', ''):
                            self._save_current_task(current_task)
                case 'developer':
                    workspace_files = node_update.get('workspace_files', {})
                    current_rev = full_state.get('revision_count', 0)
                    self._save_workspace(workspace_files, current_rev)
                case 'reviewer':
                    if review_feedback := node_update.get('review_feedback', ''):
                        current_rev = full_state.get('revision_count', 0)
                        self._save_code_review(review_feedback, current_rev)
                case 'qa':
                    if test_results := node_update.get('test_results', ''):
                        current_rev = full_state.get('revision_count', 0)
                        self._save_test_results(test_results, current_rev)
                case 'reporter':
                    if final_report := node_update.get('final_report', ''):
                        self._save_final_report(final_report)
