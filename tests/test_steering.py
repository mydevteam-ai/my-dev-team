from devteam.utils.steering import STEERING_HEADER, STEERING_RULES, steering_for


FRONTIER_SCORES = {'structured-output': 0.95, 'reasoning': 0.98, 'code-generation': 0.97}


def test_frontier_model_gets_no_steering():
    assert steering_for(FRONTIER_SCORES) == ''


def test_scores_at_threshold_clear_the_rule():
    # The comparison is strictly below: scoring exactly the threshold clears it.
    at_thresholds = {cap: below for cap, below, _ in STEERING_RULES}
    assert steering_for(at_thresholds) == ''


def test_one_low_score_fires_only_its_rule():
    # DeepSeek-like: only structured-output sits below its threshold.
    section = steering_for({**FRONTIER_SCORES, 'structured-output': 0.88})
    assert section.startswith(STEERING_HEADER)
    assert 'single tool call' in section
    assert 'step at a time' not in section
    assert 'invent file paths' not in section


def test_small_model_collects_all_rules():
    section = steering_for({'structured-output': 0.5, 'reasoning': 0.3, 'code-generation': 0.3})
    assert section.startswith(f'{STEERING_HEADER}\n\n')
    lines = section.split('\n\n', 1)[1].splitlines()
    assert lines == [f'- {line}' for _, _, line in STEERING_RULES]


def test_missing_scores_count_as_zero():
    # An unscored model gets the full set of help.
    full = steering_for({'structured-output': 0.5, 'reasoning': 0.3, 'code-generation': 0.3})
    assert steering_for({}) == full
    assert steering_for(None) == full


def test_rule_lines_contain_no_braces():
    # The section is appended to a LangChain template; the agent escapes it,
    # but braces in a rule line should not appear in the first place.
    for _, _, line in STEERING_RULES:
        assert '{' not in line and '}' not in line
