"""Tests for services/email_composer.py — subject/body building, HTML escaping, header
injection defense, and attachment MIME type. No network, no database."""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from services.email_composer import (
    build_email_message,
    build_html_body,
    build_plain_text_body,
    build_subject,
    reject_header_injection,
)
from services.email_errors import EmailContentError


@dataclass
class FakeOrder:
    order_number: str = "HIK-20260725-0001"
    order_title: str = "صيدلية العين - النجف"
    customer_name: str = "صيدلية العين"
    governorate: str = "النجف"
    selected_price_type: str = "pharmacy"
    selected_order_total: int = 562870
    generated_filename: str = "order.xlsx"
    created_at: datetime = datetime(2026, 7, 25, 9, 28, 15, tzinfo=timezone.utc)


def test_subject_default_uses_order_number_and_customer():
    subject = build_subject(FakeOrder(), None)
    assert subject == "Hikma Order HIK-20260725-0001 - صيدلية العين"


def test_subject_override_is_used_when_provided():
    subject = build_subject(FakeOrder(), "Custom Subject")
    assert subject == "Custom Subject"


def test_subject_override_rejects_header_injection():
    with pytest.raises(EmailContentError):
        build_subject(FakeOrder(), "Subject\r\nBcc: attacker@evil.com")


def test_plain_text_body_contains_key_fields():
    body = build_plain_text_body(FakeOrder(), None)
    assert "HIK-20260725-0001" in body
    assert "النجف" in body
    assert "Pharmacy Price" in body
    assert "562,870" in body
    assert "order.xlsx" in body


def test_plain_text_body_includes_optional_message():
    body = build_plain_text_body(FakeOrder(), "Please confirm receipt.")
    assert "Please confirm receipt." in body


def test_html_body_is_valid_and_contains_key_fields():
    html_body = build_html_body(FakeOrder(), None)
    assert "<html>" in html_body
    assert "HIK-20260725-0001" in html_body
    assert "Pharmacy Price" in html_body


def test_html_body_escapes_message_html():
    dangerous_message = "<script>alert('xss')</script>"
    html_body = build_html_body(FakeOrder(), dangerous_message)
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_html_body_never_contains_raw_json_or_confidence_or_row_numbers():
    html_body = build_html_body(FakeOrder(), None)
    plain_body = build_plain_text_body(FakeOrder(), None)
    for forbidden in ("confidence", "row_number", "{", "}", "matched_row"):
        assert forbidden not in html_body
        assert forbidden not in plain_body


@pytest.mark.parametrize("field_name", ["subject", "sender display name", "recipient address"])
def test_reject_header_injection_blocks_cr_lf(field_name):
    with pytest.raises(EmailContentError):
        reject_header_injection("value\r\ninjected", field_name)


def test_reject_header_injection_allows_clean_value():
    assert reject_header_injection("Clean Value", "subject") == "Clean Value"


def test_build_email_message_attaches_xlsx_with_correct_mime_type(tmp_path):
    attachment_path = tmp_path / "order.xlsx"
    attachment_path.write_bytes(b"PK\x03\x04fake xlsx bytes")

    message = build_email_message(
        order=FakeOrder(),
        from_address="orders@example.com",
        from_name="Hikma Orders",
        to_addresses=["pharmacy@example.com"],
        cc_addresses=[],
        subject="Test Subject",
        message=None,
        attachment_path=attachment_path,
        attachment_filename="order.xlsx",
    )

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.get_content_type() == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert attachment.get_filename() == "order.xlsx"
    assert attachment.get_content() == b"PK\x03\x04fake xlsx bytes"


def test_build_email_message_has_plain_and_html_alternatives(tmp_path):
    attachment_path = tmp_path / "order.xlsx"
    attachment_path.write_bytes(b"fake")

    message = build_email_message(
        order=FakeOrder(),
        from_address="orders@example.com",
        from_name="Hikma Orders",
        to_addresses=["pharmacy@example.com"],
        cc_addresses=["manager@example.com"],
        subject="Test Subject",
        message="Hello",
        attachment_path=attachment_path,
        attachment_filename="order.xlsx",
    )

    assert message["Subject"] == "Test Subject"
    assert "orders@example.com" in message["From"]
    assert message["To"] == "pharmacy@example.com"
    assert message["Cc"] == "manager@example.com"

    body = message.get_body(preferencelist=("plain",))
    assert "Hello" in body.get_content()
    html_alt = message.get_body(preferencelist=("html",))
    assert "Hello" in html_alt.get_content()
