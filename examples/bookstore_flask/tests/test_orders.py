from unittest.mock import MagicMock

from devteam_demo.services.payment import charge_card, PaymentError
import pytest


def test_charge_card_success(monkeypatch):
    fake_charge = MagicMock(status='succeeded', id='ch_123')
    monkeypatch.setattr('stripe.Charge.create', lambda **_: fake_charge)
    assert charge_card('tok_visa', 2500) == 'ch_123'


def test_charge_card_declined(monkeypatch):
    import stripe
    def raise_card_error(**_):
        raise stripe.error.CardError('declined', None, 'card_declined')
    monkeypatch.setattr('stripe.Charge.create', raise_card_error)
    with pytest.raises(PaymentError):
        charge_card('tok_bad', 2500)
