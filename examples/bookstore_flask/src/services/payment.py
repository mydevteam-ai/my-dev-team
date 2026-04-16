import stripe


class PaymentError(Exception):
    """Raised when a payment charge is declined or fails."""


def charge_card(card_token: str, amount_cents: int, currency: str = 'usd') -> str:
    """Charge a card through Stripe and return the charge id on success."""
    try:
        charge = stripe.Charge.create(
            amount=amount_cents,
            currency=currency,
            source=card_token,
            description='Bookstore order',
        )
    except stripe.error.CardError as exc:
        raise PaymentError(exc.user_message) from exc
    if charge.status != 'succeeded':
        raise PaymentError(f"Charge failed with status {charge.status}")
    return charge.id


def refund_charge(charge_id: str) -> None:
    """Refund a previously captured Stripe charge."""
    stripe.Refund.create(charge=charge_id)
