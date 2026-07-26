"""Tests for services/email_recipient_service.py — deterministic recipient validation.
No network, no database."""

import pytest

from services.email_errors import RecipientValidationError
from services.email_recipient_service import (
    MAX_CC_RECIPIENTS,
    MAX_TO_RECIPIENTS,
    MAX_TOTAL_RECIPIENTS,
    validate_and_normalize_address,
    validate_recipients,
)


def test_valid_to_address_accepted():
    to, cc = validate_recipients(["orders@example.com"], [])
    assert to == ["orders@example.com"]
    assert cc == []


def test_invalid_to_address_rejected():
    with pytest.raises(RecipientValidationError):
        validate_recipients(["not-an-email"], [])


def test_cc_addresses_supported():
    to, cc = validate_recipients(["orders@example.com"], ["manager@example.com"])
    assert to == ["orders@example.com"]
    assert cc == ["manager@example.com"]


def test_duplicate_recipients_are_normalized():
    to, cc = validate_recipients(
        ["Orders@Example.com", " orders@example.com "],
        ["orders@example.com", "manager@example.com"],
    )
    assert to == ["orders@example.com"]
    # cc address identical to a to-address is dropped, not duplicated across both lists.
    assert cc == ["manager@example.com"]


def test_no_recipients_is_rejected():
    with pytest.raises(RecipientValidationError):
        validate_recipients([], [])


def test_to_recipient_limit_enforced():
    too_many = [f"user{i}@example.com" for i in range(MAX_TO_RECIPIENTS + 1)]
    with pytest.raises(RecipientValidationError):
        validate_recipients(too_many, [])


def test_cc_recipient_limit_enforced():
    too_many = [f"user{i}@example.com" for i in range(MAX_CC_RECIPIENTS + 1)]
    with pytest.raises(RecipientValidationError):
        validate_recipients(["orders@example.com"], too_many)


def test_total_recipient_limit_enforced():
    to_addresses = [f"to{i}@example.com" for i in range(MAX_TO_RECIPIENTS)]
    cc_addresses = [f"cc{i}@example.com" for i in range(MAX_TOTAL_RECIPIENTS - MAX_TO_RECIPIENTS + 1)]
    with pytest.raises(RecipientValidationError):
        validate_recipients(to_addresses, cc_addresses)


@pytest.mark.parametrize(
    "malicious",
    [
        "orders@example.com\r\nBcc: attacker@evil.com",
        "orders@example.com\nX-Injected: true",
        "orders@example.com\r",
    ],
)
def test_header_injection_in_address_is_rejected(malicious):
    with pytest.raises(RecipientValidationError):
        validate_and_normalize_address(malicious)
