import pyotp

from devteam_demo.auth.session import promote_session, get_session
from devteam_demo.models.user import User


class InvalidTwoFactorCodeError(Exception):
    """Raised when a submitted TOTP code fails verification."""


def enroll_two_factor(user_id: int) -> str:
    """Generate a new TOTP secret for the user and return the provisioning URI."""
    secret = pyotp.random_base32()
    user = User.find_by_id(user_id)
    user.two_factor_secret = secret
    user.two_factor_enabled = True
    user.save()
    return pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name='Bookstore')


def verify_two_factor(session_token: str, code: str) -> None:
    """Verify a TOTP code for a session pending second-factor authentication."""
    record = get_session(session_token)
    if record is None or not record.get('pending_two_factor'):
        raise InvalidTwoFactorCodeError("No pending two-factor challenge for session")
    user = User.find_by_id(record['user_id'])
    if not pyotp.TOTP(user.two_factor_secret).verify(code, valid_window=1):
        raise InvalidTwoFactorCodeError("Invalid TOTP code")
    promote_session(session_token)
