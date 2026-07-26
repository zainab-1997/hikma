"""Tests for services/email_delivery_service.py — the full send orchestration.

Every test uses a temporary SQLite database and a temporary generated_orders directory
with a fake .xlsx file — none of them touch the real database or a real network
connection. SMTP is always the fake client from email_test_helpers.
"""

import smtplib

import pytest
from email_test_helpers import make_fake_smtp_class

from config.settings import Settings
from database.models import Order
from database.repositories import order_repository
from database.repositories.order_repository import OrderInput, OrderProductInput
from database.session import init_db, session_scope
from services.email_delivery_service import get_email_delivery_detail, list_email_deliveries, send_order_email
from services.email_errors import (
    EmailRecordingError,
    EmailRequestIdConflictError,
    GeneratedFileMissingError,
    OrderNotFoundForEmailError,
    RecipientValidationError,
)
from models.email_models import SendOrderEmailRequest


def _settings(**overrides) -> Settings:
    defaults = dict(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_timeout_seconds=5,
        email_from_address="orders@example.com",
        email_from_name="Hikma Orders",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _setup(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    init_db(database_url=db_url)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    return db_url, generated_dir


def _seed_order(db_url, generated_dir, *, filename="order.xlsx", write_file=True, **overrides):
    if write_file:
        (generated_dir / filename).write_bytes(b"PK\x03\x04 fake xlsx content")

    order_input_kwargs = dict(
        order_title="صيدلية العين - النجف",
        selected_price_type="pharmacy",
        selected_order_total=6000,
        generated_filename=filename,
        generated_file_id=filename,
        products=[
            OrderProductInput(
                written_product_name="Alpha",
                official_product_name="Alpha Tablet 50MG",
                worksheet_name="Sheet1",
                row_number=3,
                quantity=5,
                free_quantity=0,
            )
        ],
        customer_name="صيدلية العين",
        governorate="النجف",
    )
    order_input_kwargs.update(overrides)

    with session_scope(db_url) as session:
        order = order_repository.create_order_with_products(session, OrderInput(**order_input_kwargs))
        return order.id


def _request(**overrides) -> SendOrderEmailRequest:
    defaults = dict(
        email_request_id="req-1",
        to_addresses=["pharmacy@example.com"],
        cc_addresses=[],
        subject_override=None,
        message=None,
    )
    defaults.update(overrides)
    return SendOrderEmailRequest(**defaults)


# --- order/file resolution ------------------------------------------------------------


def test_invalid_order_id_returns_not_found_error(tmp_path):
    db_url, generated_dir = _setup(tmp_path)

    with pytest.raises(OrderNotFoundForEmailError):
        send_order_email(
            "does-not-exist", _request(), database_url=db_url, generated_orders_dir=generated_dir,
            settings=_settings(), smtp_class=make_fake_smtp_class(),
        )


def test_missing_generated_file_returns_safe_404_error(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir, write_file=False)

    with pytest.raises(GeneratedFileMissingError):
        send_order_email(
            order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
            settings=_settings(), smtp_class=make_fake_smtp_class(),
        )


def test_attachment_comes_from_saved_order_not_request(tmp_path):
    # SendOrderEmailRequest has no filename/path field at all — this proves the
    # attachment is resolved exclusively from the order's own generated_file_id.
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir, filename="the_real_saved_file.xlsx")

    sent_messages = []
    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=make_fake_smtp_class(sent_store=sent_messages),
    )

    assert result.status == "sent"
    assert len(sent_messages) == 1
    attachments = list(sent_messages[0].iter_attachments())
    assert attachments[0].get_filename() == "the_real_saved_file.xlsx"


# --- successful send --------------------------------------------------------------------


def test_successful_smtp_send_marks_delivery_sent(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=make_fake_smtp_class(),
    )

    assert result.success is True
    assert result.status == "sent"
    assert result.sent_at is not None
    assert result.order_number.startswith("HIK-")


# --- SMTP failure modes -----------------------------------------------------------------


def test_smtp_authentication_failure_marks_delivery_failed(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(
        raise_on="login", exception=smtplib.SMTPAuthenticationError(535, b"bad credentials")
    )

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert result.success is False
    assert result.status == "failed"
    assert "credentials" in result.error_message.lower()


def test_smtp_connection_failure_marks_delivery_failed(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(raise_on="connect", exception=ConnectionRefusedError("refused"))

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert result.status == "failed"
    assert "connect" in result.error_message.lower()


def test_smtp_timeout_marks_delivery_failed(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(raise_on="connect", exception=TimeoutError("timed out"))

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert result.status == "failed"
    assert "time" in result.error_message.lower()


def test_recipient_rejection_marks_delivery_failed(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(
        raise_on="send_message",
        exception=smtplib.SMTPRecipientsRefused({"pharmacy@example.com": (550, b"rejected")}),
    )

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert result.status == "failed"
    assert "recipient" in result.error_message.lower()


def test_generic_send_failure_marks_delivery_failed(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(raise_on="send_message", exception=smtplib.SMTPException("generic failure"))

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert result.status == "failed"


# --- failure never destroys anything ------------------------------------------------------


def test_failure_never_deletes_the_order(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(raise_on="connect", exception=OSError("refused"))

    send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    with session_scope(db_url) as session:
        assert session.get(Order, order_id) is not None


def test_failure_never_deletes_the_generated_file(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir, filename="keep_me.xlsx")
    fake_smtp = make_fake_smtp_class(raise_on="connect", exception=OSError("refused"))

    send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert (generated_dir / "keep_me.xlsx").exists()


def test_database_attempt_record_survives_a_send_failure(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class(raise_on="connect", exception=OSError("refused"))

    send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    deliveries = list_email_deliveries(order_id, database_url=db_url)
    assert len(deliveries) == 1
    assert deliveries[0].status == "failed"


# --- idempotency -----------------------------------------------------------------------


def test_same_email_request_id_does_not_send_twice(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    sent_messages = []
    fake_smtp = make_fake_smtp_class(sent_store=sent_messages)

    first = send_order_email(
        order_id, _request(email_request_id="req-dup"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )
    second = send_order_email(
        order_id, _request(email_request_id="req-dup"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert first.delivery_id == second.delivery_id
    assert len(sent_messages) == 1  # SMTP was only ever invoked once


def test_new_email_request_id_allows_intentional_resend(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    sent_messages = []
    fake_smtp = make_fake_smtp_class(sent_store=sent_messages)

    first = send_order_email(
        order_id, _request(email_request_id="req-1"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )
    second = send_order_email(
        order_id, _request(email_request_id="req-2"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    assert first.delivery_id != second.delivery_id
    assert len(sent_messages) == 2

    deliveries = list_email_deliveries(order_id, database_url=db_url)
    assert len(deliveries) == 2


def test_email_request_id_conflict_across_different_orders(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_a = _seed_order(db_url, generated_dir, filename="a.xlsx")
    order_b = _seed_order(db_url, generated_dir, filename="b.xlsx")
    fake_smtp = make_fake_smtp_class()

    send_order_email(
        order_a, _request(email_request_id="shared-id"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    with pytest.raises(EmailRequestIdConflictError):
        send_order_email(
            order_b, _request(email_request_id="shared-id"), database_url=db_url, generated_orders_dir=generated_dir,
            settings=_settings(), smtp_class=fake_smtp,
        )


# --- validation surfaces through the orchestration ------------------------------------------


def test_invalid_recipient_is_rejected_before_any_delivery_record(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)

    with pytest.raises(RecipientValidationError):
        send_order_email(
            order_id, _request(to_addresses=["not-an-email"]), database_url=db_url,
            generated_orders_dir=generated_dir, settings=_settings(), smtp_class=make_fake_smtp_class(),
        )

    assert list_email_deliveries(order_id, database_url=db_url) == []


# --- history endpoints (service-level) -------------------------------------------------------


def test_list_email_deliveries_returns_newest_first(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    fake_smtp = make_fake_smtp_class()

    send_order_email(
        order_id, _request(email_request_id="req-1"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )
    send_order_email(
        order_id, _request(email_request_id="req-2"), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=fake_smtp,
    )

    deliveries = list_email_deliveries(order_id, database_url=db_url)
    assert [d.attempt_number for d in deliveries] == [2, 1]


def test_get_email_delivery_detail(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)
    result = send_order_email(
        order_id, _request(message="Please confirm."), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=make_fake_smtp_class(),
    )

    detail = get_email_delivery_detail(order_id, result.delivery_id, database_url=db_url)
    assert detail is not None
    assert detail.optional_message == "Please confirm."
    assert detail.status == "sent"


# --- no secrets or paths leak into responses --------------------------------------------------


def test_response_never_contains_smtp_credentials(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(smtp_password="super-secret-password"), smtp_class=make_fake_smtp_class(),
    )

    dumped = result.model_dump_json()
    assert "super-secret-password" not in dumped
    assert "smtp_password" not in dumped


def test_response_never_contains_filesystem_paths(tmp_path):
    db_url, generated_dir = _setup(tmp_path)
    order_id = _seed_order(db_url, generated_dir)

    result = send_order_email(
        order_id, _request(), database_url=db_url, generated_orders_dir=generated_dir,
        settings=_settings(), smtp_class=make_fake_smtp_class(),
    )

    dumped = result.model_dump_json()
    assert str(generated_dir) not in dumped
    assert str(tmp_path) not in dumped
