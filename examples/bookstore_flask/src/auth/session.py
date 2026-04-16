import secrets
from datetime import datetime, timedelta, timezone

_SESSIONS: dict[str, dict] = {}
_SESSION_LIFETIME = timedelta(minutes=60)


def create_session(user_id: int, pending_two_factor: bool = False) -> str:
    """Create a new session token for the given user id."""
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = {
        'user_id': user_id,
        'created_at': datetime.now(timezone.utc),
        'pending_two_factor': pending_two_factor,
    }
    return token


def get_session(token: str) -> dict | None:
    """Return session data if the token is valid and not expired, else None."""
    record = _SESSIONS.get(token)
    if record is None:
        return None
    if datetime.now(timezone.utc) - record['created_at'] > _SESSION_LIFETIME:
        _SESSIONS.pop(token, None)
        return None
    return record


def destroy_session(token: str) -> None:
    """Remove a session from the store."""
    _SESSIONS.pop(token, None)


def promote_session(token: str) -> None:
    """Mark a session as fully authenticated after successful 2FA verification."""
    if record := _SESSIONS.get(token):
        record['pending_two_factor'] = False
