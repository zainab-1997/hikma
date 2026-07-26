"""Tests for database/repositories/email_repository.py. Every test uses a fresh
temporary SQLite file — none of them touch the real backend/database/app.db."""

from datetime import datetime, timezone

from database.models import Order
from database.repositories import email_repository, order_repository
from database.repositories.order_repository import OrderInput, OrderProductInput
from database.session import init_db, session_scope


def _db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path}/test.db"


def _seed_order(session) -> str:
    order_input = OrderInput(
        order_title="صيدلية العين - النجف",
        selected_price_type="pharmacy",
        selected_order_total=6000,
        generated_filename="order.xlsx",
        generated_file_id="order.xlsx",
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
    order = order_repository.create_order_with_products(session, order_input)
    return order.id


def _setup(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    with session_scope(url) as session:
        order_id = _seed_order(session)
    return url, order_id


def test_create_pending_delivery(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        delivery = email_repository.create_pending_delivery(
            session,
            order_id=order_id,
            email_request_id="req-1",
            to_addresses=["pharmacy@example.com"],
            cc_addresses=[],
            subject="Test Subject",
            optional_message="Hello",
        )
        delivery_id = delivery.id
        assert delivery.status == "pending"
        assert delivery.attempt_number == 1

    with session_scope(url) as session:
        deliveries = email_repository.list_deliveries_for_order(session, order_id)
        assert len(deliveries) == 1
        assert deliveries[0].id == delivery_id


def test_attempt_number_increments_per_order(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        first = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-a", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S1", optional_message=None,
        )
        assert first.attempt_number == 1

    with session_scope(url) as session:
        second = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-b", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S2", optional_message=None,
        )
        assert second.attempt_number == 2


def test_mark_sending_then_sent_updates_order_summary(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        delivery = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-1", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S1", optional_message=None,
        )
        delivery_id = delivery.id

    with session_scope(url) as session:
        email_repository.mark_sending(session, delivery_id)

    with session_scope(url) as session:
        email_repository.mark_sent(session, delivery_id, provider_message_id="msg-123")

    with session_scope(url) as session:
        deliveries = email_repository.list_deliveries_for_order(session, order_id)
        assert deliveries[0].status == "sent"
        assert deliveries[0].sent_at is not None
        assert deliveries[0].provider_message_id == "msg-123"

        order = session.get(Order, order_id)
        assert order.email_status == "sent"
        assert order.last_email_sent_at is not None


def test_mark_failed_updates_order_summary_and_keeps_order(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        delivery = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-1", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S1", optional_message=None,
        )
        delivery_id = delivery.id

    with session_scope(url) as session:
        email_repository.mark_failed(
            session, delivery_id, error_code="smtp_timeout", safe_error_message="The email server did not respond in time."
        )

    with session_scope(url) as session:
        deliveries = email_repository.list_deliveries_for_order(session, order_id)
        assert deliveries[0].status == "failed"
        assert deliveries[0].error_code == "smtp_timeout"

        order = session.get(Order, order_id)
        assert order is not None  # the order itself is never deleted on failure
        assert order.email_status == "failed"


def test_a_later_failed_attempt_does_not_clobber_the_earlier_success_timestamp(tmp_path):
    """email_status always reflects the MOST RECENT attempt's outcome; last_email_sent_at
    specifically means "the last time delivery succeeded" and is only ever set by
    mark_sent — a later failed retry must not erase or backdate it. The frontend relies
    on this: it never presents last_email_sent_at as if it were the latest attempt's own
    time when email_status is "failed"."""
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        first = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-success", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S1", optional_message=None,
        )
        email_repository.mark_sent(session, first.id)

    with session_scope(url) as session:
        order = session.get(Order, order_id)
        assert order.email_status == "sent"
        first_sent_at = order.last_email_sent_at

    with session_scope(url) as session:
        second = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-retry-fail", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S2", optional_message=None,
        )
        email_repository.mark_failed(session, second.id, error_code="smtp_timeout", safe_error_message="Timed out.")

    with session_scope(url) as session:
        order = session.get(Order, order_id)
        assert order.email_status == "failed"
        assert order.last_email_sent_at == first_sent_at  # unchanged by the later failure


def test_list_deliveries_for_order_returns_newest_first(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-1", to_addresses=["a@example.com"],
            cc_addresses=[], subject="First", optional_message=None,
        )
    with session_scope(url) as session:
        email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-2", to_addresses=["a@example.com"],
            cc_addresses=[], subject="Second", optional_message=None,
        )

    with session_scope(url) as session:
        deliveries = email_repository.list_deliveries_for_order(session, order_id)
        assert [d.subject for d in deliveries] == ["Second", "First"]


def test_find_delivery_by_request_id(tmp_path):
    url, order_id = _setup(tmp_path)

    with session_scope(url) as session:
        created = email_repository.create_pending_delivery(
            session, order_id=order_id, email_request_id="req-unique", to_addresses=["a@example.com"],
            cc_addresses=[], subject="S1", optional_message=None,
        )
        created_id = created.id

    with session_scope(url) as session:
        found = email_repository.find_delivery_by_request_id(session, "req-unique")
        assert found is not None
        assert found.id == created_id
        assert email_repository.find_delivery_by_request_id(session, "does-not-exist") is None


def test_decode_addresses_round_trips_json():
    encoded = '["a@example.com", "b@example.com"]'
    assert email_repository.decode_addresses(encoded) == ["a@example.com", "b@example.com"]
    assert email_repository.decode_addresses("") == []
