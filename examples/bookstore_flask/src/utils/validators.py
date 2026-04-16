import re


_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_ISBN_RE = re.compile(r'^(?:\d{9}[\dxX]|\d{13})$')


def is_valid_email(address: str) -> bool:
    """Return True if the string looks like a valid email address."""
    return bool(_EMAIL_RE.match(address))


def is_valid_isbn(isbn: str) -> bool:
    """Return True for a syntactically valid ISBN-10 or ISBN-13."""
    stripped = isbn.replace('-', '').replace(' ', '')
    return bool(_ISBN_RE.match(stripped))


def is_valid_username(username: str) -> bool:
    """Return True for a username of 3-64 chars of [a-zA-Z0-9_-]."""
    return bool(re.fullmatch(r'[a-zA-Z0-9_-]{3,64}', username))
