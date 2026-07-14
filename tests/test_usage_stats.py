from datetime import datetime, timezone
import pytest
from devteam.utils.usage_stats import filter_since, rollup_usage


def _call(agent='dev', model='m', input_tokens=100, output_tokens=10, cached=0,
          cost=0.01, repaired=False, context_fill=None):
    return {'agent': agent, 'model': model, 'input_tokens': input_tokens,
            'cached_tokens': cached, 'output_tokens': output_tokens, 'cost': cost,
            'context_fill': context_fill, 'repaired': repaired}


def _run(ts='2026-07-14T08:00:00+00:00', outcome='success', provider='groq',
         workflow='development', duration_s=10.0, calls=None, cost=None):
    calls = calls if calls is not None else [_call()]
    return {
        'record': 'run', 'ts': ts, 'thread_id': 't', 'workflow': workflow,
        'provider': provider, 'fanout': False, 'resumed': False, 'outcome': outcome,
        'duration_s': duration_s,
        'input_tokens': sum(c['input_tokens'] for c in calls),
        'cached_tokens': sum(c['cached_tokens'] for c in calls),
        'output_tokens': sum(c['output_tokens'] for c in calls),
        'total_cost': cost if cost is not None else sum(c['cost'] for c in calls),
        'calls': calls,
    }


# --- rollup_usage ---

def test_rollup_empty():
    stats = rollup_usage([])
    assert stats['runs'] == 0
    assert stats['overall']['calls'] == 0
    assert stats['cache_hit_rate'] == 0.0
    assert stats['repair_rate'] == 0.0
    assert stats['trends'] == []


def test_rollup_ignores_non_run_records():
    stats = rollup_usage([{'record': 'something-else'}, _run()])
    assert stats['runs'] == 1


def test_rollup_overall_totals_and_rates():
    calls = [
        _call(input_tokens=1000, cached=500, output_tokens=100, cost=0.5, repaired=True),
        _call(input_tokens=1000, cached=0, output_tokens=100, cost=0.5),
    ]
    stats = rollup_usage([_run(calls=calls)])
    overall = stats['overall']
    assert overall['calls'] == 2
    assert overall['input_tokens'] == 2000
    assert overall['total_tokens'] == 2200
    assert overall['cost'] == pytest.approx(1.0)
    assert overall['repaired'] == 1
    assert stats['cache_hit_rate'] == pytest.approx(0.25)
    assert stats['repair_rate'] == pytest.approx(0.5)


def test_rollup_call_buckets_sorted_by_tokens():
    calls = [
        _call(agent='dev', model='big', input_tokens=1000, cost=0.9),
        _call(agent='qa', model='small', input_tokens=100, cost=0.1),
    ]
    stats = rollup_usage([_run(calls=calls)])
    assert [b['key'] for b in stats['by_agent']] == ['dev', 'qa']
    assert [b['key'] for b in stats['by_model']] == ['big', 'small']
    assert stats['by_agent'][0]['cost'] == pytest.approx(0.9)


def test_rollup_run_buckets_by_outcome_provider_workflow():
    records = [
        _run(outcome='success', provider='groq', workflow='development'),
        _run(outcome='failed', provider='ollama', workflow='migration', cost=0.0),
    ]
    stats = rollup_usage(records)
    outcomes = {b['key']: b for b in stats['outcomes']}
    assert outcomes['success']['runs'] == 1
    assert outcomes['failed']['runs'] == 1
    assert {b['key'] for b in stats['by_provider']} == {'groq', 'ollama'}
    assert {b['key'] for b in stats['by_workflow']} == {'development', 'migration'}


def test_rollup_by_day_sorted_ascending():
    records = [
        _run(ts='2026-07-14T08:00:00+00:00'),
        _run(ts='2026-07-12T08:00:00+00:00'),
        _run(ts='2026-07-12T09:00:00+00:00'),
    ]
    stats = rollup_usage(records)
    assert [b['key'] for b in stats['by_day']] == ['2026-07-12', '2026-07-14']
    assert stats['by_day'][0]['runs'] == 2


def test_rollup_duration():
    stats = rollup_usage([_run(duration_s=10.0), _run(duration_s=5.5)])
    assert stats['duration']['runs_timed'] == 2
    assert stats['duration']['total_s'] == pytest.approx(15.5)


def test_rollup_trends_count_runs_affected():
    # 'dev' thrashes (>5 calls) in two runs, 'qa' in none.
    thrashing_calls = [_call(agent='dev') for _ in range(6)]
    records = [
        _run(calls=thrashing_calls),
        _run(calls=thrashing_calls),
        _run(calls=[_call(agent='qa')]),
    ]
    stats = rollup_usage(records)
    thrash = [t for t in stats['trends'] if t['kind'] == 'thrashing']
    assert len(thrash) == 1
    assert thrash[0]['agent'] == 'dev'
    assert thrash[0]['runs_affected'] == 2
    assert thrash[0]['total_runs'] == 3


def test_rollup_tolerates_missing_optional_fields():
    # A minimal record (e.g. hand-trimmed or from an older version) must not crash the rollup.
    stats = rollup_usage([{'record': 'run', 'calls': [
        {'agent': 'dev', 'input_tokens': 10, 'output_tokens': 1}]}])
    assert stats['runs'] == 1
    assert stats['overall']['cost'] == 0


# --- filter_since ---

def test_filter_since_keeps_recent_drops_old():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _run(ts='2026-07-13T08:00:00+00:00'),
        _run(ts='2026-07-01T08:00:00+00:00'),
    ]
    kept = filter_since(records, days=7, now=now)
    assert len(kept) == 1
    assert kept[0]['ts'].startswith('2026-07-13')


def test_filter_since_drops_records_with_bad_timestamp():
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    records = [{'record': 'run'}, {'record': 'run', 'ts': 'not-a-date'}]
    assert filter_since(records, days=7, now=now) == []
