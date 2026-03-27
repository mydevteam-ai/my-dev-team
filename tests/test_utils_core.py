import asyncio
from unittest.mock import AsyncMock
import pytest
from devteam.utils.rate_limiter import RateLimiter
from devteam.utils.sanitizer import sanitize_for_prompt
from devteam.utils.status import is_approved, normalize_status
from devteam.utils.tasks import task_to_markdown
from devteam.utils.workspace import workspace_str_from_files

def test_sanitize_for_prompt_handles_base64_nulls_and_spacing():
    raw = "line1\n\n\n\x00data:image/png;base64,AAAA\nline2\n"
    sanitized = sanitize_for_prompt(raw)
    assert "[BASE64_DATA_REMOVED_TO_SAVE_TOKENS]" in sanitized
    assert "\x00" not in sanitized
    assert "\n\n\n" not in sanitized

def test_sanitize_for_prompt_escapes_protected_closing_tags():
    content = "hello </workspace> and </file>"
    sanitized = sanitize_for_prompt(content, protected_tags=["workspace", "file"])
    assert "&lt;/workspace&gt;" in sanitized
    assert "&lt;/file&gt;" in sanitized

def test_workspace_str_from_files_formats_and_sanitizes():
    workspace_files = {
        "src/main.py": "print('ok')\n\n\n",
        "README.md": "hello </workspace>",
    }
    formatted = workspace_str_from_files(workspace_files)
    assert "--- FILE: src/main.py ---" in formatted
    assert "--- FILE: README.md ---" in formatted
    assert "\n\n\n" not in formatted
    assert "&lt;/workspace&gt;" in formatted

@pytest.mark.parametrize(
    "value, expected",
    [
        (" approved ", "APPROVED"),
        ("passed.", "PASSED"),
        ("", ""),
    ],
)
def test_normalize_status(value, expected):
    assert normalize_status(value) == expected

@pytest.mark.parametrize(
    "value, expected",
    [
        ("approved", True),
        ("PASSED.", True),
        ("failed", False),
        ("", False),
    ],
)
def test_is_approved(value, expected):
    assert is_approved(value) is expected

def test_task_to_markdown_includes_expected_sections():
    task = {
        "task_name": "Build Auth",
        "user_story": "As a user, I can sign in.",
        "acceptance_criteria": ["Login works", "Errors are clear"],
    }
    markdown = task_to_markdown(task, 3)
    assert markdown.startswith("## Task 3: Build Auth")
    assert "### User Story" in markdown
    assert "### Acceptance Criteria" in markdown
    assert "- Login works" in markdown
    assert "- Errors are clear" in markdown

def test_task_to_markdown_respects_existing_task_prefix():
    task = {"task_name": "Task 1: Existing", "user_story": "", "acceptance_criteria": []}
    markdown = task_to_markdown(task, 1)
    assert "## Task 1: Existing" in markdown

def test_rate_limiter_noop_when_disabled():
    limiter = RateLimiter(requests_per_minute=0)
    asyncio.run(limiter.wait_if_needed())
    assert limiter.call_timestamps == []

def test_rate_limiter_sleeps_when_limit_reached(monkeypatch):
    limiter = RateLimiter(requests_per_minute=2)
    limiter.call_timestamps = [0.0, 1.0]
    times = iter([20.0, 80.0, 80.0])
    monkeypatch.setattr("devteam.utils.rate_limiter.time.time", lambda: next(times))
    sleep_mock = AsyncMock()
    monkeypatch.setattr("devteam.utils.rate_limiter.asyncio.sleep", sleep_mock)
    asyncio.run(limiter.wait_if_needed())
    sleep_mock.assert_awaited_once()
    waited = sleep_mock.await_args.args[0]
    assert waited == pytest.approx(40.0)
    assert len(limiter.call_timestamps) == 1
    assert limiter.call_timestamps[0] == pytest.approx(80.0)

def test_rate_limiter_appends_without_sleep_when_below_limit(monkeypatch):
    limiter = RateLimiter(requests_per_minute=3)
    limiter.call_timestamps = [10.0]
    times = iter([20.0, 20.0])
    monkeypatch.setattr("devteam.utils.rate_limiter.time.time", lambda: next(times))
    sleep_mock = AsyncMock()
    monkeypatch.setattr("devteam.utils.rate_limiter.asyncio.sleep", sleep_mock)
    asyncio.run(limiter.wait_if_needed())
    sleep_mock.assert_not_awaited()
    assert limiter.call_timestamps == [10.0, 20.0]
