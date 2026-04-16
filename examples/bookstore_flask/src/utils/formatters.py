def format_currency(amount_cents: int, currency: str = 'USD') -> str:
    """Format an integer amount of cents as a human-readable price string."""
    symbol = {'USD': '$', 'EUR': '€', 'GBP': '£'}.get(currency, '')
    return f"{symbol}{amount_cents / 100:.2f}"


def format_isbn(isbn: str) -> str:
    """Normalise an ISBN into the canonical dashed form for display."""
    digits = isbn.replace('-', '').replace(' ', '')
    if len(digits) == 13:
        return f"{digits[:3]}-{digits[3]}-{digits[4:8]}-{digits[8:12]}-{digits[12]}"
    return digits
