"""All SQL/ORM access for email delivery attempts lives here — no other module talks to
the email_deliveries table directly.

Recipient lists are stored as JSON text on the row (see database.models.EmailDelivery)
but every function here works in terms of plain Python lists — callers never touch the
JSON encoding.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import EmailDelivery, Order


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def find_delivery_by_request_id(session: Session, email_request_id: str) -> EmailDelivery | None:
    if not email_request_id:
        return None
    return session.execute(
        select(EmailDelivery).where(EmailDelivery.email_request_id == email_request_id)
    ).scalar_one_or_none()


def get_delivery(session: Session, order_id: str, delivery_id: str) -> EmailDelivery | None:
    return session.execute(
        select(EmailDelivery).where(EmailDelivery.id == delivery_id, EmailDelivery.order_id == order_id)
    ).scalar_one_or_none()


def list_deliveries_for_order(session: Session, order_id: str) -> list[EmailDelivery]:
    return list(
        session.execute(
            select(EmailDelivery)
            .where(EmailDelivery.order_id == order_id)
            .order_by(EmailDelivery.created_at.desc())
        ).scalars()
    )


def _next_attempt_number(session: Session, order_id: str) -> int:
    count = session.execute(
        select(func.count()).select_from(EmailDelivery).where(EmailDelivery.order_id == order_id)
    ).scalar_one()
    return count + 1


def create_pending_delivery(
    session: Session,
    *,
    order_id: str,
    email_request_id: str,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    optional_message: str | None,
) -> EmailDelivery:
    delivery = EmailDelivery(
        order_id=order_id,
        email_request_id=email_request_id,
        attempt_number=_next_attempt_number(session, order_id),
        status="pending",
        to_addresses=json.dumps(to_addresses),
        cc_addresses=json.dumps(cc_addresses),
        subject=subject,
        optional_message=optional_message,
        created_at=_utcnow(),
    )
    session.add(delivery)
    session.flush()
    return delivery


def mark_sending(session: Session, delivery_id: str) -> EmailDelivery:
    delivery = session.get(EmailDelivery, delivery_id)
    delivery.status = "sending"
    session.flush()
    return delivery


def mark_sent(session: Session, delivery_id: str, *, provider_message_id: str | None = None) -> EmailDelivery:
    delivery = session.get(EmailDelivery, delivery_id)
    delivery.status = "sent"
    delivery.sent_at = _utcnow()
    delivery.provider_message_id = provider_message_id
    session.flush()

    order = session.get(Order, delivery.order_id)
    order.email_status = "sent"
    order.last_email_sent_at = delivery.sent_at
    session.flush()

    return delivery


def mark_failed(session: Session, delivery_id: str, *, error_code: str, safe_error_message: str) -> EmailDelivery:
    delivery = session.get(EmailDelivery, delivery_id)
    delivery.status = "failed"
    delivery.error_code = error_code
    delivery.safe_error_message = safe_error_message
    session.flush()

    order = session.get(Order, delivery.order_id)
    order.email_status = "failed"
    session.flush()

    return delivery


def decode_addresses(raw_json: str) -> list[str]:
    if not raw_json:
        return []
    return json.loads(raw_json)
