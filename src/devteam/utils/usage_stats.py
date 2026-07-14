"""Pure aggregation over the persistent run log - no I/O, no rich.

The pipeline analog of my-dev-team-vs-code's usageStats.ts: the same rollup
serves the CLI report and any future GUI usage page, and staying free of the
file system and rendering is what makes it trivially unit-testable. Consumes
the records `utils/run_log.py` stores (header totals plus raw per-call
records) and recomputes diagnostics per stored run via the shared pure
`collect_diagnostics`, so trends reach across runs, not just within one.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from .cost_optimization import collect_diagnostics


def filter_since(records: list[dict], days: int, now: datetime | None = None) -> list[dict]:
    """Records whose timestamp falls within the last `days` days."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    kept = []
    for record in records:
        try:
            ts = datetime.fromisoformat(record['ts'])
        except (KeyError, TypeError, ValueError):
            continue
        if ts >= cutoff:
            kept.append(record)
    return kept


def _empty_call_bucket() -> dict:
    return {'calls': 0, 'input_tokens': 0, 'cached_tokens': 0, 'output_tokens': 0,
            'total_tokens': 0, 'cost': 0.0, 'repaired': 0}


def _add_call(bucket: dict, call: dict) -> None:
    bucket['calls'] += 1
    bucket['input_tokens'] += call.get('input_tokens', 0)
    bucket['cached_tokens'] += call.get('cached_tokens', 0)
    bucket['output_tokens'] += call.get('output_tokens', 0)
    bucket['total_tokens'] = bucket['input_tokens'] + bucket['output_tokens']
    bucket['cost'] += call.get('cost', 0) or 0
    if call.get('repaired'):
        bucket['repaired'] += 1


def _empty_run_bucket() -> dict:
    return {'runs': 0, 'total_tokens': 0, 'cost': 0.0}


def _add_run(bucket: dict, record: dict) -> None:
    bucket['runs'] += 1
    bucket['total_tokens'] += record.get('input_tokens', 0) + record.get('output_tokens', 0)
    bucket['cost'] += record.get('total_cost', 0) or 0


def _to_buckets(buckets: dict[str, dict]) -> list[dict]:
    """key->bucket map to a list sorted by total tokens, descending."""
    return sorted(
        ({'key': key, **bucket} for key, bucket in buckets.items()),
        key=lambda b: b['total_tokens'], reverse=True,
    )


def rollup_usage(records: list[dict]) -> dict:
    """Roll every run record up into overall totals, breakdowns and cross-run trends."""
    overall = _empty_call_bucket()
    by_agent: dict[str, dict] = defaultdict(_empty_call_bucket)
    by_model: dict[str, dict] = defaultdict(_empty_call_bucket)
    by_provider: dict[str, dict] = defaultdict(_empty_run_bucket)
    by_workflow: dict[str, dict] = defaultdict(_empty_run_bucket)
    by_day: dict[str, dict] = defaultdict(_empty_run_bucket)
    outcomes: dict[str, dict] = defaultdict(_empty_run_bucket)
    duration = {'runs_timed': 0, 'total_s': 0.0}
    # (kind, agent) -> number of runs the diagnostic fired in
    trend_counts: dict[tuple[str, str], int] = defaultdict(int)
    runs = 0
    for record in records:
        if record.get('record') != 'run':
            continue
        runs += 1
        _add_run(by_provider[record.get('provider', 'unknown')], record)
        _add_run(by_workflow[record.get('workflow', 'unknown')], record)
        _add_run(by_day[str(record.get('ts', ''))[:10] or 'unknown'], record)
        _add_run(outcomes[record.get('outcome', 'unknown')], record)
        if isinstance(record.get('duration_s'), (int, float)):
            duration['runs_timed'] += 1
            duration['total_s'] += record['duration_s']
        calls = record.get('calls') or []
        for call in calls:
            _add_call(overall, call)
            _add_call(by_agent[call.get('agent', 'unknown')], call)
            _add_call(by_model[call.get('model', 'unknown')], call)
        for diagnostic in collect_diagnostics(calls):
            trend_counts[(diagnostic['kind'], diagnostic['agent'])] += 1

    trends = sorted(
        ({'kind': kind, 'agent': agent, 'runs_affected': count, 'total_runs': runs}
         for (kind, agent), count in trend_counts.items()),
        key=lambda t: t['runs_affected'], reverse=True,
    )
    return {
        'runs': runs,
        'overall': overall,
        'cache_hit_rate': overall['cached_tokens'] / overall['input_tokens'] if overall['input_tokens'] else 0.0,
        'repair_rate': overall['repaired'] / overall['calls'] if overall['calls'] else 0.0,
        'duration': duration,
        'outcomes': _to_buckets(outcomes),
        'by_agent': _to_buckets(by_agent),
        'by_model': _to_buckets(by_model),
        'by_provider': _to_buckets(by_provider),
        'by_workflow': _to_buckets(by_workflow),
        'by_day': sorted(_to_buckets(by_day), key=lambda b: b['key']),
        'trends': trends,
    }
