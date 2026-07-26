"""Thin wrapper around smtplib so email_delivery_service can be tested with a fake SMTP
client — no real network connection, ever, in automated tests.

Only marks a send as successful once send_message() completes without raising; opening a
connection is never treated as success on its own.
"""

import smtplib
import ssl
from email.message import EmailMessage


class SmtpSendError(Exception):
    def __init__(self, error_code: str, safe_message: str):
        super().__init__(safe_message)
        self.error_code = error_code
        self.safe_message = safe_message


def send_email_message(
    message: EmailMessage,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    use_ssl: bool,
    timeout_seconds: int,
    smtp_class=None,
    smtp_ssl_class=None,
) -> None:
    """Raises SmtpSendError (never a raw smtplib/socket exception) on any failure.
    smtp_class/smtp_ssl_class are injectable so tests can pass a fake, context-manager
    compatible client instead of ever touching a real socket."""
    smtp_class = smtp_class or smtplib.SMTP
    smtp_ssl_class = smtp_ssl_class or smtplib.SMTP_SSL

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtp_ssl_class(host, port, timeout=timeout_seconds, context=context) as client:
                if username:
                    client.login(username, password)
                client.send_message(message)
        else:
            with smtp_class(host, port, timeout=timeout_seconds) as client:
                if use_tls:
                    client.starttls(context=ssl.create_default_context())
                if username:
                    client.login(username, password)
                client.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpSendError(
            "smtp_authentication_failed", "The email server rejected the configured credentials."
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise SmtpSendError("recipient_rejected", "The email server rejected one or more recipients.") from exc
    except smtplib.SMTPConnectError as exc:
        raise SmtpSendError("smtp_connection_failed", "Could not connect to the email server.") from exc
    except TimeoutError as exc:
        # socket.timeout is an alias for TimeoutError since Python 3.10 — one clause covers both.
        raise SmtpSendError("smtp_timeout", "The email server did not respond in time.") from exc
    except smtplib.SMTPException as exc:
        raise SmtpSendError("smtp_send_failed", "The email could not be sent.") from exc
    except OSError as exc:
        raise SmtpSendError("smtp_connection_failed", "Could not connect to the email server.") from exc
