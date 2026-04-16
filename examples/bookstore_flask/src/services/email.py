import smtplib
from email.message import EmailMessage


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send a plaintext email via the configured SMTP server."""
    message = EmailMessage()
    message['From'] = 'no-reply@bookstore.example'
    message['To'] = to_address
    message['Subject'] = subject
    message.set_content(body)
    with smtplib.SMTP('smtp.mailgun.org', 587) as smtp:
        smtp.starttls()
        smtp.send_message(message)


def send_order_confirmation(to_address: str, order_id: int, total_cents: int) -> None:
    """Send an order confirmation email to the customer."""
    subject = f"Order #{order_id} confirmed"
    body = f"Thank you for your order. Total charged: ${total_cents / 100:.2f}"
    send_email(to_address, subject, body)


def send_password_reset(to_address: str, reset_link: str) -> None:
    """Send a password-reset link to a user."""
    send_email(to_address, 'Reset your password', f"Click the link to reset: {reset_link}")
