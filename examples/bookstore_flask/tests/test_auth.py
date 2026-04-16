import pytest

from devteam_demo.auth.login import login, InvalidCredentialsError
from devteam_demo.auth.password import hash_password, verify_password


def test_verify_password_roundtrip():
    hashed = hash_password('correct horse battery staple')
    assert verify_password('correct horse battery staple', hashed)
    assert not verify_password('wrong guess', hashed)


def test_login_rejects_unknown_user(monkeypatch):
    monkeypatch.setattr('devteam_demo.models.user.User.find_by_username', lambda name: None)
    with pytest.raises(InvalidCredentialsError):
        login('ghost', 'irrelevant')


def test_login_rejects_bad_password(monkeypatch, fake_user):
    monkeypatch.setattr('devteam_demo.models.user.User.find_by_username', lambda name: fake_user)
    with pytest.raises(InvalidCredentialsError):
        login(fake_user.username, 'wrong-password')
