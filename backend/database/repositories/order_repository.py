"""All SQL/ORM access for orders and their product lines lives here — no other module
talks to the orders/order_products tables directly.

Order numbers use the human-readable HIK-YYYYMMDD-NNNN format, sequential per UTC day.
The count-then-insert approach below is safe for SQLite's single-writer model (the only
deployment target at this stage); create_order_with_products retries a handful of times
on a unique-constraint collision as a defensive measure, not because contention is
expected in practice.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from database.models import Order, OrderProduct

_MAX_ORDER_NUMBER_ATTEMPTS = 5


@dataclass(frozen=True)
class OrderProductInput:
    written_product_name: str
    official_product_name: str
    worksheet_name: str
    row_number: int
    quantity: int
    free_quantity: int
    free_percentage: float | None = None
    product_note: str | None = None
    match_status: str | None = None
    match_score: float | None = None


@dataclass(frozen=True)
class OrderInput:
    order_title: str
    selected_price_type: str
    selected_order_total: int
    generated_filename: str
    generated_file_id: str
    products: list[OrderProductInput]
    customer_name: str | None = None
    customer_type: str | None = None
    governorate: str | None = None
    city: str | None = None
    area: str | None = None
    phone_number: str | None = None
    is_transit: bool = False
    primary_customer: str | None = None
    destination_customer: str | None = None
    source_location: str | None = None
    destination_location: str | None = None
    destination_governorate: str | None = None
    destination_city: str | None = None
    destination_area: str | None = None
    excluded_order_notes: bool = False
    source_message: str | None = None
    parser_confidence_score: float | None = None
    client_request_id: str | None = None


def find_order_by_client_request_id(session: Session, client_request_id: str) -> Order | None:
    if not client_request_id:
        return None
    return session.execute(
        select(Order).where(Order.client_request_id == client_request_id)
    ).scalar_one_or_none()


def _count_orders_for_prefix(session: Session, prefix: str) -> int:
    return session.execute(
        select(func.count()).select_from(Order).where(Order.order_number.like(f"{prefix}%"))
    ).scalar_one()


def generate_order_number(session: Session, reference_date: datetime | None = None, offset: int = 0) -> str:
    reference_date = reference_date or datetime.now(timezone.utc)
    prefix = f"HIK-{reference_date.strftime('%Y%m%d')}-"
    count = _count_orders_for_prefix(session, prefix)
    return f"{prefix}{count + 1 + offset:04d}"


def create_order_with_products(session: Session, order_input: OrderInput) -> Order:
    """Insert the order header and all product lines as a single flush.

    Caller owns the transaction boundary (see database.session.session_scope) — this
    function only flushes so integrity errors surface here for the order-number retry
    loop, and the caller's commit/rollback still governs the whole unit of work.
    """
    now = datetime.now(timezone.utc)
    last_error: IntegrityError | None = None

    for attempt in range(_MAX_ORDER_NUMBER_ATTEMPTS):
        order_number = generate_order_number(session, now, offset=attempt)
        order = Order(
            id=str(uuid.uuid4()),
            order_number=order_number,
            client_request_id=order_input.client_request_id,
            customer_name=order_input.customer_name,
            customer_type=order_input.customer_type,
            governorate=order_input.governorate,
            city=order_input.city,
            area=order_input.area,
            phone_number=order_input.phone_number,
            order_title=order_input.order_title,
            is_transit=order_input.is_transit,
            primary_customer=order_input.primary_customer,
            destination_customer=order_input.destination_customer,
            source_location=order_input.source_location,
            destination_location=order_input.destination_location,
            destination_governorate=order_input.destination_governorate,
            destination_city=order_input.destination_city,
            destination_area=order_input.destination_area,
            selected_price_type=order_input.selected_price_type,
            selected_order_total=order_input.selected_order_total,
            generated_filename=order_input.generated_filename,
            generated_file_id=order_input.generated_file_id,
            excluded_order_notes=order_input.excluded_order_notes,
            source_message=order_input.source_message,
            parser_confidence_score=order_input.parser_confidence_score,
            status="generated",
            created_at=now,
            updated_at=now,
            products=[
                OrderProduct(
                    id=str(uuid.uuid4()),
                    written_product_name=p.written_product_name,
                    official_product_name=p.official_product_name,
                    worksheet_name=p.worksheet_name,
                    row_number=p.row_number,
                    quantity=p.quantity,
                    free_quantity=p.free_quantity,
                    free_percentage=p.free_percentage,
                    product_note=p.product_note,
                    match_status=p.match_status,
                    match_score=p.match_score,
                    created_at=now,
                )
                for p in order_input.products
            ],
        )

        session.add(order)
        try:
            session.flush()
            return order
        except IntegrityError as exc:
            session.rollback()
            last_error = exc
            continue

    raise last_error


def get_order_by_id(session: Session, order_id: str) -> Order | None:
    return session.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.products))
    ).scalar_one_or_none()


def list_orders(
    session: Session,
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
) -> tuple[list[Order], int]:
    query = select(Order)

    if customer_name:
        query = query.where(Order.customer_name.ilike(f"%{customer_name}%"))
    if governorate:
        query = query.where(Order.governorate.ilike(f"%{governorate}%"))
    if customer_type:
        query = query.where(Order.customer_type == customer_type)
    if price_type:
        query = query.where(Order.selected_price_type == price_type)
    if date_from:
        query = query.where(Order.created_at >= date_from)
    if date_to:
        query = query.where(Order.created_at <= date_to)
    if search:
        needle = f"%{search}%"
        query = query.where(
            Order.order_number.ilike(needle)
            | Order.customer_name.ilike(needle)
            | Order.order_title.ilike(needle)
        )

    total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    page_query = query.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    orders = session.execute(page_query).scalars().all()
    return list(orders), total
