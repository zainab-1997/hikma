"""Tests for services/email_config_service.py — configuration validation only, no
network access and no database involved."""

import pytest

from config.settings import Settings
from services.email_config_service import validate_email_configuration
from services.email_errors import EmailConfigurationError


def _settings(**overrides) -> Settings:
    defaults = dict(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_timeout_seconds=20,
        email_from_address="orders@example.com",
        email_from_name="Hikma Orders",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_valid_configuration_passes():
    validate_email_configuration(_settings())  # must not raise


def test_email_disabled_blocks_sending():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(email_enabled=False))


def test_missing_smtp_host_blocks_sending():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(smtp_host=""))


def test_missing_sender_address_blocks_sending():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(email_from_address=""))


def test_invalid_sender_address_is_rejected():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(email_from_address="not-an-email"))


def test_tls_and_ssl_simultaneously_enabled_is_rejected():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(smtp_use_tls=True, smtp_use_ssl=True))


def test_invalid_port_is_rejected():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(smtp_port=0))
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(smtp_port=70000))


def test_invalid_timeout_is_rejected():
    with pytest.raises(EmailConfigurationError):
        validate_email_configuration(_settings(smtp_timeout_seconds=0))
