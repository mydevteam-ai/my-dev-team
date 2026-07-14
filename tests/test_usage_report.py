import json
from devteam.cli.usage_report import _bucket_table, _format_duration, _totals_panel, _trends_panel, show_usage_report
from devteam.utils.run_log import RunLog
from devteam.utils.usage_stats import rollup_usage


def _sample_records():
    calls = [{'agent': 'dev', 'model': 'm', 'input_tokens': 6000, 'cached_tokens': 500,
              'output_tokens': 10, 'cost': 0.5, 'context_fill': 0.9, 'repaired': True}]
    return [{'record': 'run', 'ts': '2026-07-14T08:00:00+00:00', 'thread_id': 't',
             'workflow': 'development', 'provider': 'groq', 'fanout': False,
             'resumed': False, 'outcome': 'success', 'duration_s': 65.0,
             'input_tokens': 6000, 'cached_tokens': 500, 'output_tokens': 10,
             'total_cost': 0.5, 'calls': calls}]


def test_format_duration():
    assert _format_duration(59) == '59s'
    assert _format_duration(65) == '1m 5s'
    assert _format_duration(3700) == '1h 1m'


def test_panels_render():
    stats = rollup_usage(_sample_records())
    assert _totals_panel(stats).border_style == 'blue'
    assert _bucket_table("BY AGENT", "Agent", stats['by_agent'], run_level=False)
    assert _bucket_table("BY DAY", "Day", stats['by_day'], run_level=True)
    # The sample run trips high_waste + context_pressure + output_repair.
    assert _trends_panel(stats).border_style == 'red'


def test_trends_panel_green_when_clean():
    stats = rollup_usage([])
    assert _trends_panel(stats).border_style == 'green'


def test_show_usage_report_smoke(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'run-log.jsonl'
    monkeypatch.setattr('devteam.cli.usage_report.RunLog', lambda: RunLog(path))
    show_usage_report()
    assert 'No run records found' in capsys.readouterr().out

    path.write_text('\n'.join(json.dumps(r) for r in _sample_records()) + '\n', encoding='utf-8')
    show_usage_report()
    out = capsys.readouterr().out
    assert 'USAGE TOTALS' in out
    assert 'BY AGENT' in out
    assert 'CROSS-RUN TRENDS' in out
