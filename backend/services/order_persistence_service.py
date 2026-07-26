"""Persists successfully generated orders (and their product lines) to SQLite.

Guarantees:
- An order is only ever recorded in the database *after* its Excel file has already been
  generated successfully. If generation fails, nothing is written to the database.
- If persistence itself then fails, the just-generated file is deleted (cleanup
  strategy A: never leave an orphaned, unrecorded file on disk — chosen over "keep and
  mark orphaned" because a file with no database row is otherwise unreachable through any
  API in this app anyway, so retaining it would only be dead weight, not a recoverable
  asset). The caller is told plainly that the file was removed.
- client_request_id gives idempotent retries: a repeat of the same request returns the
  already-saved order and never re-generates or re-persists anything.
"""

import logging
from datetime import datetime, timezone

from database.repositories import order_repository
from database.repositories.order_repository import OrderInput, OrderProductInput
from database.session import session_scope
from excel.order_writer import ExcelGenerationError
from models.generate_order_models import GenerateOrderRequest, GeneratedOrderResponse
from models.order_history_models import OrderDetail, OrderListResponse, OrderProductDetail, OrderSummary
from services.excel_generation_service import delete_generated_file, generate_excel_order

logger = logging.getLogger(__name__)


class PersistenceError(ExcelGenerationError):
    """Raised when a generated order could not be saved to the database. By the time
    this is raised, the Excel file generated for this request has already been deleted."""

    status_code = 500


def _order_input_from_request(request: GenerateOrderRequest, generation) -> OrderInput:
    return OrderInput(
        order_title=request.order_title,
        selected_price_type=request.selected_price_type,
        selected_order_total=generation.selected_order_total,
        generated_filename=generation.filename,
        generated_file_id=generation.filename,
        excluded_order_notes=generation.excluded_order_notes,
        customer_name=request.customer_name,
        customer_type=request.customer_type,
        governorate=request.governorate,
        area=request.area,
        phone_number=request.phone_number,
        is_transit=request.is_transit,
        primary_customer=request.primary_customer,
        destination_customer=request.destination_customer,
        source_message=request.source_message,
        parser_confidence_score=request.parser_confidence_score,
        client_request_id=request.client_request_id,
        products=[
            OrderProductInput(
                written_product_name=product.written_product_name,
                official_product_name=product.matched_official_name,
                worksheet_name="Sheet1",
                row_number=product.matched_row,
                quantity=product.quantity,
                free_quantity=product.free_quantity,
                free_percentage=product.free_percentage,
                product_note=product.notes,
                match_status=product.match_status,
                match_score=product.match_score,
            )
            for product in request.products
        ],
    )


def _order_to_response(order) -> GeneratedOrderResponse:
    created_at = order.created_at
    if created_at.tzinfo is None:
        # SQLite stores UTC timestamps without an offset. Normalize reloads so an
        # idempotent retry is byte-for-byte equivalent to the original API response.
        created_at = created_at.replace(tzinfo=timezone.utc)
    return GeneratedOrderResponse(
        order_id=order.id,
        order_number=order.order_number,
        filename=order.generated_filename,
        download_url=f"/api/orders/download/{order.generated_file_id}",
        selected_price_type=order.selected_price_type,
        selected_order_total=order.selected_order_total,
        created_at=created_at,
        excluded_order_notes=order.excluded_order_notes,
    )


def generate_and_persist_order(
    request: GenerateOrderRequest, *, database_url: str | None = None, **generation_kwargs
) -> GeneratedOrderResponse:
    """database_url and **generation_kwargs (catalog/source_path/output_dir) are
    overridable so tests never need the real database or the real Hikma template."""
    if request.client_request_id:
        with session_scope(database_url) as session:
            existing = order_repository.find_order_by_client_request_id(session, request.client_request_id)
            if existing is not None:
                return _order_to_response(existing)

    # May raise ExcelGenerationError — propagates untouched; no order is ever created
    # for a request whose Excel generation failed.
    generation = generate_excel_order(request, **generation_kwargs)

    order_input = _order_input_from_request(request, generation)

    try:
        with session_scope(database_url) as session:
            order = order_repository.create_order_with_products(session, order_input)
            response = _order_to_response(order)
    except Exception as exc:
        deleted = delete_generated_file(generation.filename, base_dir=generation_kwargs.get("output_dir"))
        # Two simultaneous deliveries of the same idempotency key can both pass the
        # initial lookup before either transaction commits. The database uniqueness
        # constraint chooses the winner; the loser discards its generated file and
        # returns the winner exactly like any other retry.
        if request.client_request_id:
            with session_scope(database_url) as session:
                existing = order_repository.find_order_by_client_request_id(
                    session, request.client_request_id
                )
                if existing is not None:
                    return _order_to_response(existing)
        logger.exception(
            "Failed to persist generated order (file %s, cleanup deleted=%s).", generation.filename, deleted
        )
        raise PersistenceError(
            "The Excel file was generated but the order could not be saved, so it was "
            "removed. Please try again."
        ) from exc

    return response


def _to_summary(order) -> OrderSummary:
    return OrderSummary(
        order_id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_type=order.customer_type,
        governorate=order.governorate,
        selected_price_type=order.selected_price_type,
        selected_order_total=order.selected_order_total,
        created_at=order.created_at,
        download_url=f"/api/orders/download/{order.generated_file_id}",
        email_status=order.email_status,
        last_email_sent_at=order.last_email_sent_at,
    )


def _to_detail(order) -> OrderDetail:
    return OrderDetail(
        order_id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_type=order.customer_type,
        governorate=order.governorate,
        area=order.area,
        phone_number=order.phone_number,
        order_title=order.order_title,
        is_transit=order.is_transit,
        primary_customer=order.primary_customer,
        destination_customer=order.destination_customer,
        selected_price_type=order.selected_price_type,
        selected_order_total=order.selected_order_total,
        generated_filename=order.generated_filename,
        download_url=f"/api/orders/download/{order.generated_file_id}",
        created_at=order.created_at,
        email_status=order.email_status,
        last_email_sent_at=order.last_email_sent_at,
        products=[
            OrderProductDetail(
                written_product_name=p.written_product_name,
                official_product_name=p.official_product_name,
                row_number=p.row_number,
                quantity=p.quantity,
                free_quantity=p.free_quantity,
                free_percentage=p.free_percentage,
                product_note=p.product_note,
                match_status=p.match_status,
                match_score=p.match_score,
            )
            for p in order.products
        ],
    )


def list_order_summaries(
    *,
    customer_name: str | None = None,
    governorate: str | None = None,
    customer_type: str | None = None,
    price_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    database_url: str | None = None,
) -> OrderListResponse:
    with session_scope(database_url) as session:
        orders, total = order_repository.list_orders(
            session,
            customer_name=customer_name,
            governorate=governorate,
            customer_type=customer_type,
            price_type=price_type,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=offset,
        )
        summaries = [_to_summary(order) for order in orders]

    return OrderListResponse(orders=summaries, total=total, limit=limit, offset=offset)


def get_order_detail(order_id: str, *, database_url: str | None = None) -> OrderDetail | None:
    with session_scope(database_url) as session:
        order = order_repository.get_order_by_id(session, order_id)
        if order is None:
            return None
        return _to_detail(order)


def get_order_generated_file_id(order_id: str, *, database_url: str | None = None) -> str | None:
    with session_scope(database_url) as session:
        order = order_repository.get_order_by_id(session, order_id)
        return order.generated_file_id if order is not None else None
