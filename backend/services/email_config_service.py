"""Validates SMTP/email configuration before attempting to send.

Kept separate from config/settings.py so a disabled or misconfigured email setup never
prevents the rest of the app from starting — only email-sending itself fails, with a
clear, safe message, exactly as EMAIL_ENABLED=false is supposed to behave.
"""

import re

from config.settings import Settings
from services.email_errors import EmailConfigurationError

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email_configuration(settings: Settings) -> None:
    if not settings.email_enabled:
        raise EmailConfigurationError("Email delivery is currently disabled.")

    if not settings.smtp_host.strip():
        raise EmailConfigurationError("Email delivery is not fully configured (missing SMTP host).")

    if not settings.email_from_address.strip():
        raise EmailConfigurationError("Email delivery is not fully configured (missing sender address).")

    if not _EMAIL_PATTERN.match(settings.email_from_address.strip()):
        raise EmailConfigurationError("Email delivery is not fully configured (invalid sender address).")

    if settings.smtp_use_tls and settings.smtp_use_ssl:
        raise EmailConfigurationError("Email delivery is misconfigured (TLS and SSL cannot both be enabled).")

    if not (1 <= settings.smtp_port <= 65535):
        raise EmailConfigurationError("Email delivery is not fully configured (invalid SMTP port).")

    if settings.smtp_timeout_seconds <= 0:
        raise EmailConfigurationError("Email delivery is not fully configured (invalid SMTP timeout).")
