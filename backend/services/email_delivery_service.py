"""Orchestrates emailing a saved, already-generated order.

Sending is an external side effect that cannot be wrapped in the same database
transaction as the record update, so this uses an explicit state machine with its own
commit at each step instead of one big transaction:

  1. Look up email_request_id — a repeat returns the prior result untouched (no re-send).
  2. Load the order; resolve its generated file through the existing safe resolver.
  3. Validate recipients and content.
  4. Insert an EmailDelivery row with status="pending".            [commit]
  5. Flip it to status="sending".                                  [commit]
  6. Attempt the SMTP send.
  7. Flip it to "sent" (+ sent_at, provider id) or "failed"
     (+ error_code, safe_error_message).                           [commit]

Unexpected process termination: if the process dies between step 5's commit and step 7's
commit (mid-send, or if the final status update itself fails to persist — see
EmailRecordingError below), the row is left at status="sending" indefinitely. This is a
known, documented limitation: no reconciliation job exists yet to detect or resolve a
stuck "sending" row, and because the email may or may not have actually reached the SMTP
server before the interruption, Order History deliberately shows "sending" rather than
guessing "sent" or "failed" — a human needs to check the mailbox/SMTP provider logs to
resolve it. A future task should add a reconciliation sweep (e.g. anything "sending" for
more than N minutes gets flagged) — not implemented here as it wasn't requested.

An email is only ever marked "sent" after send_email_message() returns without raising —
opening an SMTP connection is never treated as success on its own.
"""

import logging

from database.repositories import email_repository, order_repository
from database.session import session_scope
from services.email_composer import build_email_message, build_subject
from services.email_config_service import validate_email_configuration
from services.email_errors import (
    EmailRecordingError,
    EmailRequestIdConflictError,
    GeneratedFileMissingError,
    OrderNotFoundForEmailError,
)
from services.email_recipient_service import validate_recipients
from excel.order_writer import ExcelGenerationError
from config.settings import get_settings
from models.email_models import EmailDeliveryDetail, EmailDeliverySummary, SendOrderEmailRequest, SendOrderEmailResponse
from services.excel_generation_service import resolve_generated_file_path
from services.smtp_client import SmtpSendError, send_email_message

logger = logging.getLogger(__name__)


def _summary_from_delivery(delivery) -> EmailDeliverySummary:
    return EmailDeliverySummary(
        delivery_id=delivery.id,
        order_id=delivery.order_id,
        attempt_number=delivery.attempt_number,
        status=delivery.status,
        to_addresses=email_repository.decode_addresses(delivery.to_addresses),
        cc_addresses=email_repository.decode_addresses(delivery.cc_addresses),
        subject=delivery.subject,
        created_at=delivery.created_at,
        sent_at=delivery.sent_at,
        safe_error_message=delivery.safe_error_message,
    )


def _detail_from_delivery(delivery) -> EmailDeliveryDetail:
    summary = _summary_from_delivery(delivery)
    return EmailDeliveryDetail(
        **summary.model_dump(),
        optional_message=delivery.optional_message,
        error_code=delivery.error_code,
    )


def _response_from_delivery(delivery, order_number: str) -> SendOrderEmailResponse:
    return SendOrderEmailResponse(
        success=delivery.status == "sent",
        delivery_id=delivery.id,
        order_id=delivery.order_id,
        order_number=order_number,
        status=delivery.status,
        to_addresses=email_repository.decode_addresses(delivery.to_addresses),
        cc_addresses=email_repository.decode_addresses(delivery.cc_addresses),
        subject=delivery.subject,
        sent_at=delivery.sent_at,
        error_message=delivery.safe_error_message,
    )


def send_order_email(
    order_id: str,
    request: SendOrderEmailRequest,
    *,
    database_url: str | None = None,
    generated_orders_dir=None,
    smtp_class=None,
    smtp_ssl_class=None,
    settings=None,
) -> SendOrderEmailResponse:
    """database_url/generated_orders_dir/smtp_class/smtp_ssl_class/settings are all
    overridable so tests never need the real database, the real generated_orders
    directory, a real network connection, or the real (email-disabled-by-default)
    environment configuration."""
    settings = settings if settings is not None else get_settings()
    validate_email_configuration(settings)

    # Idempotency: a repeat of the same email_request_id returns the prior result and
    # never sends again, whether that attempt succeeded or failed. If it was recorded
    # against a DIFFERENT order, that's a genuine conflict, not a legitimate replay.
    with session_scope(database_url) as session:
        existing = email_repository.find_delivery_by_request_id(session, request.email_request_id)
        if existing is not None:
            if existing.order_id != order_id:
                raise EmailRequestIdConflictError(
                    "This email_request_id was already used for a different order."
                )
            order = order_repository.get_order_by_id(session, order_id)
            return _response_from_delivery(existing, order.order_number)

    with session_scope(database_url) as session:
        order = order_repository.get_order_by_id(session, order_id)
        if order is None:
            raise OrderNotFoundForEmailError("Order not found.")
        # Detached but still usable after the session closes (expire_on_commit=False).
        order_snapshot = order

    try:
        file_path = resolve_generated_file_path(order_snapshot.generated_file_id, base_dir=generated_orders_dir)
    except ExcelGenerationError as exc:
        raise GeneratedFileMissingError("The generated Excel file for this order was not found.") from exc
    if not file_path.is_file():
        raise GeneratedFileMissingError("The generated Excel file for this order was not found.")

    to_addresses, cc_addresses = validate_recipients(request.to_addresses, request.cc_addresses)
    subject = build_subject(order_snapshot, request.subject_override)

    with session_scope(database_url) as session:
        delivery = email_repository.create_pending_delivery(
            session,
            order_id=order_snapshot.id,
            email_request_id=request.email_request_id,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            optional_message=request.message,
        )
        delivery_id = delivery.id

    with session_scope(database_url) as session:
        email_repository.mark_sending(session, delivery_id)

    email_message = build_email_message(
        order=order_snapshot,
        from_address=settings.email_from_address,
        from_name=settings.email_from_name,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=subject,
        message=request.message,
        attachment_path=file_path,
        attachment_filename=order_snapshot.generated_filename,
    )

    try:
        send_email_message(
            email_message,
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
            timeout_seconds=settings.smtp_timeout_seconds,
            smtp_class=smtp_class,
            smtp_ssl_class=smtp_ssl_class,
        )
    except SmtpSendError as exc:
        logger.error(
            "Email send failed for order %s (delivery %s, %d recipients): %s",
            order_snapshot.order_number,
            delivery_id,
            len(to_addresses) + len(cc_addresses),
            exc.error_code,
        )
        return _record_outcome(
            database_url, delivery_id, order_snapshot.order_number, status="failed",
            error_code=exc.error_code, safe_error_message=exc.safe_message,
        )
    except Exception:
        logger.exception(
            "Unexpected error sending email for order %s (delivery %s).",
            order_snapshot.order_number,
            delivery_id,
        )
        return _record_outcome(
            database_url, delivery_id, order_snapshot.order_number, status="failed",
            error_code="unexpected_error",
            safe_error_message="The email could not be sent due to an unexpected error.",
        )

    return _record_outcome(database_url, delivery_id, order_snapshot.order_number, status="sent")


def _record_outcome(
    database_url: str | None,
    delivery_id: str,
    order_number: str,
    *,
    status: str,
    error_code: str | None = None,
    safe_error_message: str | None = None,
) -> SendOrderEmailResponse:
    """Persists the final outcome. If THIS commit itself fails, the delivery row is left
    at "sending" (see module docstring) and the caller is told plainly that the send
    outcome could not be confirmed — never silently reported as success."""
    try:
        with session_scope(database_url) as session:
            if status == "sent":
                delivery = email_repository.mark_sent(session, delivery_id)
            else:
                delivery = email_repository.mark_failed(
                    session, delivery_id, error_code=error_code, safe_error_message=safe_error_message
                )
            return _response_from_delivery(delivery, order_number)
    except Exception as exc:
        logger.exception("Failed to record email delivery outcome for delivery %s.", delivery_id)
        raise EmailRecordingError(
            "The email send outcome could not be saved. Check Order History before resending."
        ) from exc


def list_email_deliveries(order_id: str, *, database_url: str | None = None) -> list[EmailDeliverySummary]:
    with session_scope(database_url) as session:
        order = order_repository.get_order_by_id(session, order_id)
        if order is None:
            raise OrderNotFoundForEmailError("Order not found.")
        deliveries = email_repository.list_deliveries_for_order(session, order_id)
        return [_summary_from_delivery(delivery) for delivery in deliveries]


def get_email_delivery_detail(
    order_id: str, delivery_id: str, *, database_url: str | None = None
) -> EmailDeliveryDetail | None:
    with session_scope(database_url) as session:
        order = order_repository.get_order_by_id(session, order_id)
        if order is None:
            raise OrderNotFoundForEmailError("Order not found.")
        delivery = email_repository.get_delivery(session, order_id, delivery_id)
        if delivery is None:
            return None
        return _detail_from_delivery(delivery)
