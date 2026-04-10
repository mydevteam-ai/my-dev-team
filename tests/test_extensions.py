import asyncio
from pathlib import Path
import threading
from queue import Queue
from unittest.mock import MagicMock
from devteam.extensions.console_logger import _format_value, ConsoleLogger
from devteam.extensions.hitl_cli import HumanInTheLoop
from devteam.extensions.hitl_gui import HumanInTheLoopGUI
from devteam.extensions.workspace_saver import WorkspaceSaver
from devteam.state import TaskContext

def test_format_value_pending_tasks_summary():
    value = [{"task_name": "Auth"}, {"task_name": "API"}]
    formatted = _format_value("pending_tasks", value)
    assert formatted == "[2 task(s): Auth, API]"

def test_format_value_truncates_large_known_fields():
    long_text = "x" * 250
    formatted = _format_value("specs", long_text)
    assert formatted.endswith("... (250 chars)")
    assert len(formatted) < 250

def test_console_logger_on_step_skips_empty_values(monkeypatch):
    logger = ConsoleLogger()
    print_mock = MagicMock()
    monkeypatch.setattr("devteam.extensions.console_logger.print", print_mock)

    state_update = {
        "developer": {
            "specs": "",
            "current_task": "Implement auth",
        }
    }
    full_state = {"communication_log": ["[DEV] Working on auth"]}

    asyncio.run(logger.on_step("thread-1", state_update, full_state))

    # One panel for node output + one line for latest communication log.
    assert print_mock.call_count == 2


def test_workspace_saver_target_dir_rules(tmp_path: Path):
    saver = WorkspaceSaver(tmp_path)

    assert saver._get_target_dir({'current_phase': 'planning'}) == tmp_path / "00_planning"
    assert saver._get_target_dir({'current_phase': 'integration'}) == tmp_path / "90_integration"
    assert saver._get_target_dir({'current_phase': 'complete'}) == tmp_path / "90_integration"
    assert saver._get_target_dir({'current_phase': 'development', 'task_context': TaskContext(current_task_index=3)}) == tmp_path / "03_task"
    assert saver._get_target_dir({'current_phase': 'development'}) == tmp_path / "01_task"
    assert saver._get_target_dir({}) == tmp_path / "00_planning"


def test_workspace_saver_on_start_saves_requirements(tmp_path: Path):
    saver = WorkspaceSaver(tmp_path)

    asyncio.run(saver.on_start("thread-1", {"requirements": "Build auth module"}))

    requirements_file = tmp_path / "00_planning" / "requirements.md"
    assert requirements_file.exists()
    assert requirements_file.read_text(encoding="utf-8") == "Build auth module"


def test_workspace_saver_on_step_saves_all_outputs(tmp_path: Path):
    saver = WorkspaceSaver(tmp_path)
    asyncio.run(saver.on_start("thread-1", {"requirements": "R"}))

    asyncio.run(saver.on_step(
        "thread-1",
        {
            "pm": {"specs": "Spec content"},
            "architect": {
                "pending_tasks": [
                    {
                        "task_name": "Build API",
                        "user_story": "As a user, I need API access",
                        "acceptance_criteria": ["Returns 200"],
                    }
                ]
            },
        },
        {"current_phase": "planning"},
    ))

    asyncio.run(saver.on_step(
        "thread-1",
        {
            "developer": {
                "task_context": TaskContext(changed_files={"src/main.py": "print('ok')"}),
            },
            "reviewer": {"task_context": TaskContext(review_feedback="Looks good")},
            "qa": {"task_context": TaskContext(test_results="PASSED")},
        },
        {"current_phase": "development", "task_context": TaskContext(current_task_index=1, revision_count=2)},
    ))

    asyncio.run(saver.on_step(
        "thread-1",
        {"reporter": {"final_report": "Final summary"}},
        {"current_phase": "integration", "current_task_index": 1},
    ))

    assert (tmp_path / "00_planning" / "specs.md").read_text(encoding="utf-8") == "Spec content"
    assert (tmp_path / "00_planning" / "tasks.md").exists()
    assert (tmp_path / "01_task" / "rev_2" / "src" / "main.py").read_text(encoding="utf-8") == "print('ok')"
    assert (tmp_path / "01_task" / "feedback_v2.md").read_text(encoding="utf-8") == "Looks good"
    assert (tmp_path / "01_task" / "test_results_v2.md").read_text(encoding="utf-8") == "PASSED"
    assert (tmp_path / "90_integration" / "final_report.md").read_text(encoding="utf-8") == "Final summary"


def test_hitl_cli_handles_planning_pause_with_clarification(monkeypatch):
    ext = HumanInTheLoop()
    monkeypatch.setattr('builtins.input', lambda _: 'Use only integer operations')
    update = asyncio.run(ext.on_pause(
        'thread-1',
        {'clarification_question': 'Should division return floats?'},
        'human',
    ))
    assert update['messages'][0].content == 'Use only integer operations'
    assert update['communication_log'][0] == '**[HumanInTheLoop]**: Use only integer operations'


def test_hitl_cli_ignores_non_human_pause():
    ext = HumanInTheLoop()
    update = asyncio.run(ext.on_pause(
        'thread-1',
        {'clarification_question': ''},
        'other',
    ))
    assert update is None


def test_hitl_gui_handles_planning_pause_with_clarification():
    event_queue = Queue()
    ext = HumanInTheLoopGUI(event_queue)

    timer = threading.Timer(0.05, ext.submit_response, args=('Build only a CLI version',))
    timer.start()
    try:
        update = asyncio.run(ext.on_pause(
            'thread-1',
            {'clarification_question': 'CLI or GUI calculator?'},
            'human',
        ))
    finally:
        timer.cancel()

    queued_event = event_queue.get(timeout=1)
    assert queued_event['type'] == 'hitl_request'
    assert queued_event['question'] == 'CLI or GUI calculator?'
    assert update['messages'][0].content == 'Build only a CLI version'
    assert update['communication_log'][0] == '**[HumanInTheLoopGUI]**: Build only a CLI version'
