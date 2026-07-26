"""Deterministic recipient validation and normalization for outgoing order emails.

The frontend may *suggest* recipients, but every address is re-validated here — nothing
from the request is trusted as-is.
"""

import re

from services.email_errors import RecipientValidationError

MAX_TO_RECIPIENTS = 10
MAX_CC_RECIPIENTS = 10
MAX_TOTAL_RECIPIENTS = 20

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_HEADER_INJECTION_PATTERN = re.compile(r"[\r\n]")


def validate_and_normalize_address(raw: str) -> str:
    if not raw or not raw.strip():
        raise RecipientValidationError("A recipient email address is required.")
    if _HEADER_INJECTION_PATTERN.search(raw):
        raise RecipientValidationError("Recipient addresses must not contain line breaks.")

    candidate = raw.strip().lower()
    if not _EMAIL_PATTERN.match(candidate):
        raise RecipientValidationError(f'"{raw.strip()}" is not a valid email address.')
    return candidate


def _normalize_unique(raw_addresses: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in raw_addresses:
        address = validate_and_normalize_address(raw)
        if address not in seen:
            seen.add(address)
            normalized.append(address)
    return normalized


def validate_recipients(to_addresses: list[str], cc_addresses: list[str]) -> tuple[list[str], list[str]]:
    """Returns (to, cc), both normalized (lowercased, deduplicated), with any cc address
    that's already a To address dropped from cc. Raises RecipientValidationError for any
    problem — no recipients, an invalid address, or a limit exceeded."""
    to_normalized = _normalize_unique(to_addresses)
    cc_normalized = [addr for addr in _normalize_unique(cc_addresses) if addr not in to_normalized]

    if not to_normalized:
        raise RecipientValidationError("At least one recipient (To) is required.")

    if len(to_normalized) > MAX_TO_RECIPIENTS:
        raise RecipientValidationError(f"A maximum of {MAX_TO_RECIPIENTS} To recipients is allowed.")

    if len(cc_normalized) > MAX_CC_RECIPIENTS:
        raise RecipientValidationError(f"A maximum of {MAX_CC_RECIPIENTS} CC recipients is allowed.")

    total = len(to_normalized) + len(cc_normalized)
    if total > MAX_TOTAL_RECIPIENTS:
        raise RecipientValidationError(f"A maximum of {MAX_TOTAL_RECIPIENTS} total recipients is allowed.")

    return to_normalized, cc_normalized
