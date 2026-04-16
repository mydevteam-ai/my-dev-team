import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt with a per-password salt."""
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def password_strength(plain: str) -> int:
    """Return a naive strength score 0-4 for a plaintext password."""
    score = 0
    if len(plain) >= 12:
        score += 1
    if any(c.isupper() for c in plain) and any(c.islower() for c in plain):
        score += 1
    if any(c.isdigit() for c in plain):
        score += 1
    if any(not c.isalnum() for c in plain):
        score += 1
    return score
