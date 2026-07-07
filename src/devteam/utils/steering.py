"""Capability-derived model steering (ported from my-dev-team-vs-code's
engine/config/steering.ts).

The agent prompts describe *what* an agent does and assume a capable model;
they do not change with the model. A weaker model needs extra nudging to hit
the same bar - stricter output formatting, more explicit step-by-step
reasoning, less guessing. Rather than fork a whole prompt per model (an
agents x models matrix that drifts), a small extra "Model-specific guidance"
section is derived from the *routed model's* capability scores in llms.yaml:
each rule fires only when the model scores below its threshold, so a frontier
model (Opus/GPT-5.5/Gemini Pro) clears every threshold and gets an empty
section (extra hand-holding tends to make a strong model verbose or
over-cautious), a strong open/cloud model (e.g. DeepSeek) picks up a line or
two, and a small local model collects most of them.

A newly registered model needs no steering config - its capability scores in
the shared registry decide automatically. The thresholds sit just above where
the frontier models score; edit them here to retune the split. The rule texts
are app-local code for now, like vs-code's - moving them into the shared
my-dev-team-config library is TODO 1.6.
"""

STEERING_HEADER = '## Model-specific guidance'

# (capability, threshold, guidance line): the line is added when the routed
# model's score for the capability is below the threshold. The reasoning and
# code-generation lines match vs-code's verbatim; the structured-output line
# is adapted to this app's native tool-calling contract (the failure modes
# coerce_tool_calls and NoToolCallError exist to patch).
STEERING_RULES: tuple[tuple[str, float, str], ...] = (
    ('structured-output', 0.9,
     'Submit your result as a single tool call with valid JSON arguments - '
     'no plain-text JSON, no prose or markdown around the call.'),
    ('reasoning', 0.8,
     'Work through the problem one step at a time before you act or answer. '
     'Do not skip steps or guess at a conclusion you have not reasoned out.'),
    ('code-generation', 0.85,
     'Do not invent file paths, APIs, function names or identifiers. When you '
     'are not certain something exists, use a tool to verify it rather than '
     'assuming.'),
)


def steering_for(capabilities: dict) -> str:
    """The steering section for a routed model's capability scores.

    Returns the lines for every rule whose capability the model scores below
    threshold (a missing score counts as 0, so an unscored model gets the full
    set of help), or an empty string when the model clears every threshold -
    a strong model's prompt is left untouched.
    """
    caps = capabilities or {}
    lines = [f'- {line}' for cap, below, line in STEERING_RULES
             if caps.get(cap, 0.0) < below]
    if not lines:
        return ''
    return f"{STEERING_HEADER}\n\n" + '\n'.join(lines)
