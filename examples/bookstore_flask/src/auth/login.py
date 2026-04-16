from devteam_demo.auth.password import verify_password
from devteam_demo.auth.session import create_session
from devteam_demo.models.user import User


class InvalidCredentialsError(Exception):
    """Raised when the supplied username or password does not match."""


def login(username: str, password: str) -> str:
    """Authenticate a user by username and password and return a session token.

    Raises InvalidCredentialsError on unknown user or password mismatch.
    """
    user = User.find_by_username(username)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")
    if user.two_factor_enabled:
        return create_session(user.id, pending_two_factor=True)
    return create_session(user.id)


def logout(session_token: str) -> None:
    """Invalidate an active session token."""
    from devteam_demo.auth.session import destroy_session
    destroy_session(session_token)
