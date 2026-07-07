"""Outgoing request throttling and 429 retry support (the throttle predates
the port; the per-provider budgets and the retry helpers are ported from
my-dev-team-vs-code's engine/core/rateLimiter.ts).

Two behaviours, both per provider:

  - Throttle (`RateLimiter`): rolling one-minute windows keyed by the routed
    model's real provider, so a compound provider like `free` never spends the
    Groq budget on its local Ollama calls. A provider's budget resolves as the
    user's `--rpm` override when set, else the provider's default from the
    shared registry (the `rpm` key of its llms.yaml section), else 0 = no
    throttle.
  - Retry (module functions): a 429 is detected across the provider SDKs'
    error shapes and the retry delay is taken from the response's
    `retry-after-ms`/`retry-after` headers or the "try again in Ns" message
    hint (Groq phrases its limit this way), falling back to exponential
    backoff. The retry loop itself lives in BaseAgent._invoke_llm, bounded by
    MAX_RATE_LIMIT_RETRIES.
"""
import asyncio
import re
import time
from email.utils import parsedate_to_datetime
from .with_logging import WithLogging

# Retry bounds, mirroring vs-code's limits.provider values. Compile-time
# constants like there - the cost is a few bounded sleeps, not a tuning knob.
MAX_RATE_LIMIT_RETRIES = 5
MAX_RETRY_WAIT = 60.0   # cap on a single retry wait, seconds
RETRY_BUFFER = 0.25     # added to a provider-suggested delay (it is approximate)

_RETRY_HINT_PATTERN = re.compile(r'try again in ([\d.]+)\s*(ms|s)\b', re.IGNORECASE)
_RATE_LIMIT_MESSAGE_PATTERN = re.compile(r'rate limit|status code 429|\b429\b', re.IGNORECASE)


def is_rate_limit_error(exc: BaseException) -> bool:
    """Whether an exception is a provider rate-limit rejection (HTTP 429).

    Each SDK raises its own class (openai/groq/anthropic RateLimitError carry
    `status_code`, google's errors carry `code`, httpx errors carry the status
    on `response`), so detection is duck-typed, with rate-limit wording in the
    message as the last resort for wrapped errors.
    """
    for attr in ('status_code', 'code'):
        if getattr(exc, attr, None) == 429:
            return True
    if getattr(getattr(exc, 'response', None), 'status_code', None) == 429:
        return True
    return bool(_RATE_LIMIT_MESSAGE_PATTERN.search(str(exc)))


def suggested_delay(exc: BaseException) -> float | None:
    """The retry delay a 429 response suggests, in seconds, or None when it
    carries none. Reads the standard `retry-after-ms` / `retry-after` headers
    (seconds or an HTTP date) off the error's response, then falls back to
    parsing the provider's "try again in Ns" message hint."""
    headers = getattr(getattr(exc, 'response', None), 'headers', None) or {}
    try:
        ms = float(headers.get('retry-after-ms'))
        if ms >= 0:
            return ms / 1000.0
    except (TypeError, ValueError):
        pass
    if after := headers.get('retry-after'):
        try:
            return max(0.0, float(after))
        except ValueError:
            pass
        try:
            return max(0.0, parsedate_to_datetime(after).timestamp() - time.time())
        except ValueError:
            pass
    if match := _RETRY_HINT_PATTERN.search(str(exc)):
        value = float(match.group(1))
        return value / 1000.0 if match.group(2).lower() == 'ms' else value
    return None


def retry_delay(exc: BaseException, attempt: int) -> float | None:
    """How long to wait (seconds) before retrying a rate-limited call on this
    `attempt` (0-based), or None when the error is not a rate limit. Prefers
    the provider's suggested delay plus a small buffer; otherwise backs off
    exponentially. Always clamped to MAX_RETRY_WAIT."""
    if not is_rate_limit_error(exc):
        return None
    suggested = suggested_delay(exc)
    wait = suggested + RETRY_BUFFER if suggested is not None else float(2 ** attempt)
    return min(MAX_RETRY_WAIT, max(0.0, wait))


class RateLimiter(WithLogging):
    """
    Prevents the crew from exceeding API rate limits using per-provider
    rolling time windows.

    `provider_defaults` maps real provider names to their registry default
    budgets (LLMFactory.provider_rpm_defaults); `requests_per_minute` is the
    user's `--rpm` override and, when > 0, wins over every default.
    """
    def __init__(self, requests_per_minute: int = 0, provider_defaults: dict[str, int] = None):
        self.rpm_limit = requests_per_minute
        self.provider_defaults = provider_defaults or {}
        self.call_timestamps: dict[str, list[float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def rpm_for(self, provider: str) -> int:
        """The effective requests-per-minute budget for a provider."""
        if self.rpm_limit > 0:
            return self.rpm_limit
        return int(self.provider_defaults.get(provider) or 0)

    async def wait_if_needed(self, provider: str = None):
        key = provider or '_default'
        rpm = self.rpm_for(key)
        if rpm <= 0:
            return
        # One lock per provider: a Groq window sleep must not block a
        # concurrent Ollama call's bookkeeping.
        async with self._locks.setdefault(key, asyncio.Lock()):
            current_time = time.time()
            timestamps = [t for t in self.call_timestamps.get(key, []) if current_time - t < 60.0]
            if len(timestamps) >= rpm:
                sleep_time = 60.0 - (current_time - timestamps[0])
                if sleep_time > 0:
                    self.logger.warning("Rate limit reached for %s (%i RPM). Pausing for %i seconds...", key, rpm, sleep_time)
                    await asyncio.sleep(sleep_time)
                current_time = time.time()
                timestamps = [t for t in timestamps if current_time - t < 60.0]
            timestamps.append(time.time())
            self.call_timestamps[key] = timestamps
