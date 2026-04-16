from devteam_demo.utils.validators import is_valid_email, is_valid_isbn, is_valid_username


def test_email_validator_accepts_valid_addresses():
    assert is_valid_email('alice@example.com')
    assert is_valid_email('first.last+tag@sub.example.co.uk')


def test_email_validator_rejects_bad_input():
    assert not is_valid_email('no-at-sign')
    assert not is_valid_email('')


def test_isbn_validator():
    assert is_valid_isbn('9780131103627')
    assert is_valid_isbn('0-306-40615-2')
    assert not is_valid_isbn('abc-def')


def test_username_validator():
    assert is_valid_username('alice_99')
    assert not is_valid_username('al')
    assert not is_valid_username('space name')
