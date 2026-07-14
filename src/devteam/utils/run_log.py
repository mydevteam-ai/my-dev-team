"""Persistent run log: one JSONL record per finished run under ~/.devteam/.

The pipeline analog of my-dev-team-vs-code's eval log (client/evalLog.ts):
each record carries the run's header (thread id, workflow, provider, outcome,
duration, token/cost totals) plus the tracker's raw per-call records, so
later report changes apply retroactively to stored history. Privacy by
construction: no requirements text, no prompt or workspace content - only
routing labels, model names, token counts and outcomes, and the file never
leaves the machine.

Writes must never break the run they measure: append() swallows every
exception, and the reader skips malformed lines so one truncated write never
hides the rest of the history.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from devteam import settings

logger = logging.getLogger(__name__)

RUN_LOG_FILENAME = 'run-log.jsonl'

# How a run ended, as the calling surface saw it.
RUN_OUTCOMES = ('success', 'failed', 'aborted', 'interrupted', 'error')


def default_run_log_path() -> Path:
    """The log's home, next to the global config.yaml."""
    return Path.home() / '.devteam' / RUN_LOG_FILENAME


class RunLog:
    """Append-only JSONL store for run records."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_run_log_path()

    def append(self, record: dict) -> None:
        """Append one record as a single JSON line. Never raises."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to append run record to %s", self.path)

    def read_records(self) -> list[dict]:
        """Every stored record, oldest first. Missing file yields []; malformed lines are skipped."""
        try:
            text = self.path.read_text(encoding='utf-8')
        except OSError:
            return []
        records = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records


def build_run_record(telemetry, request, thread_id: str, outcome: str,
                     duration_s: float, error: str | None = None) -> dict:
    """Assemble one run record from the tracker and the run's request/outcome."""
    record = {
        'record': 'run',
        'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'thread_id': thread_id,
        'workflow': request.workflow,
        'provider': request.provider,
        'fanout': request.fanout,
        'resumed': request.kind == 'resume',
        'outcome': outcome,
        'duration_s': round(duration_s, 1),
        'total_requests': telemetry.total_requests,
        'repaired_calls': telemetry.repaired_calls,
        'input_tokens': telemetry.input_tokens,
        'cached_tokens': telemetry.cached_tokens,
        'output_tokens': telemetry.output_tokens,
        'total_cost': round(telemetry.total_cost, 6),
        'calls': list(telemetry.call_history),
    }
    if error:
        record['error'] = str(error)[:500]
    return record


def write_run_record(telemetry, request, thread_id: str, outcome: str,
                     started_monotonic: float, error: str | None = None) -> None:
    """Build and append the run record from a surface's finally block. Never raises.

    Gated on the `run_log` setting; a run that never reached an LLM call
    (e.g. an immediate startup failure) is not recorded.
    """
    try:
        if not settings.run_log or not telemetry.total_requests:
            return
        record = build_run_record(
            telemetry, request, thread_id, outcome,
            duration_s=time.monotonic() - started_monotonic, error=error,
        )
        RunLog().append(record)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to write run record for thread %s", thread_id)
