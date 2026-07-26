"""Deterministic, read-only SQLAlchemy analytics queries.

All aggregation stays in SQL. SQLite-specific period expressions are isolated in
``_period_expression`` so a future database migration has one obvious adaptation point.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Integer, Select, case, distinct, exists, func, select
from sqlalchemy.orm import Session

from database.models import EmailDelivery, Order, OrderProduct

UNKNOWN = "Unknown"


@dataclass(frozen=True)
class AnalyticsFilters:
    date_from: datetime | None = None
    date_to_exclusive: datetime | None = None
    governorate: str | None = None
    customer_type: str | None = None
    selected_price_type: str | None = None
    customer_name: str | None = None
    product_name: str | None = None


def _apply_order_filters(query: Select, filters: AnalyticsFilters) -> Select:
    if filters.date_from:
        query = query.where(Order.created_at >= filters.date_from)
    if filters.date_to_exclusive:
        query = query.where(Order.created_at < filters.date_to_exclusive)
    if filters.governorate:
        query = query.where(Order.governorate == filters.governorate)
    if filters.customer_type:
        query = query.where(Order.customer_type == filters.customer_type)
    if filters.selected_price_type:
        query = query.where(Order.selected_price_type == filters.selected_price_type)
    if filters.customer_name:
        query = query.where(Order.customer_name.ilike(f"%{filters.customer_name}%"))
    if filters.product_name:
        query = query.where(
            exists(
                select(1).where(
                    OrderProduct.order_id == Order.id,
                    OrderProduct.official_product_name.ilike(f"%{filters.product_name}%"),
                )
            )
        )
    return query


def _filtered_order_ids(filters: AnalyticsFilters) -> Select:
    return _apply_order_filters(select(Order.id), filters)


def overview(session: Session, filters: AnalyticsFilters) -> dict:
    order_row = session.execute(
        _apply_order_filters(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.selected_order_total), 0),
                func.coalesce(func.avg(Order.selected_order_total), 0),
                func.count(distinct(case((func.trim(func.coalesce(Order.customer_name, "")) != "", Order.customer_name)))),
                func.count(distinct(case((func.trim(func.coalesce(Order.governorate, "")) != "", Order.governorate)))),
            ),
            filters,
        )
    ).one()
    quantity_row = session.execute(
        select(
            func.coalesce(func.sum(OrderProduct.quantity), 0),
            func.coalesce(func.sum(OrderProduct.free_quantity), 0),
        ).where(OrderProduct.order_id.in_(_filtered_order_ids(filters)))
    ).one()
    email_row = session.execute(
        select(
            func.coalesce(func.sum(case((EmailDelivery.status == "sent", 1), else_=0)), 0),
            func.coalesce(func.sum(case((EmailDelivery.status == "failed", 1), else_=0)), 0),
        ).where(EmailDelivery.order_id.in_(_filtered_order_ids(filters)))
    ).one()
    return {
        "total_orders": order_row[0],
        "total_sales_value": order_row[1],
        "average_order_value": order_row[2],
        "unique_customers": order_row[3],
        "unique_governorates": order_row[4],
        "total_ordered_quantity": quantity_row[0],
        "total_free_quantity": quantity_row[1],
        "sent_email_count": email_row[0],
        "failed_email_count": email_row[1],
    }


def _period_expression(granularity: str):
    if granularity == "daily":
        return func.date(Order.created_at)
    if granularity == "monthly":
        return func.strftime("%Y-%m", Order.created_at)
    # Monday-start ISO-style week, represented by its YYYY-MM-DD start date.
    days_since_monday = (func.cast(func.strftime("%w", Order.created_at), Integer) + 6) % 7
    return func.date(Order.created_at, func.printf("-%d days", days_since_monday))


def sales_over_time(session: Session, filters: AnalyticsFilters, granularity: str) -> list[dict]:
    period = _period_expression(granularity).label("period")
    order_aggregate = (
        _apply_order_filters(
            select(
                Order.id.label("order_id"),
                period,
                Order.selected_order_total.label("sales"),
            ),
            filters,
        )
    ).subquery()
    quantities = (
        select(
            OrderProduct.order_id.label("order_id"),
            func.sum(OrderProduct.quantity).label("ordered_quantity"),
            func.sum(OrderProduct.free_quantity).label("free_quantity"),
        )
        .group_by(OrderProduct.order_id)
        .subquery()
    )
    rows = session.execute(
        select(
            order_aggregate.c.period,
            func.count(order_aggregate.c.order_id),
            func.coalesce(func.sum(order_aggregate.c.sales), 0),
            func.coalesce(func.sum(quantities.c.ordered_quantity), 0),
            func.coalesce(func.sum(quantities.c.free_quantity), 0),
        )
        .outerjoin(quantities, quantities.c.order_id == order_aggregate.c.order_id)
        .group_by(order_aggregate.c.period)
        .order_by(order_aggregate.c.period)
    ).all()
    return [dict(zip(("period", "order_count", "sales_total", "ordered_quantity", "free_quantity"), row)) for row in rows]


def by_governorate(session: Session, filters: AnalyticsFilters) -> list[dict]:
    label = case(
        (func.trim(func.coalesce(Order.governorate, "")) == "", UNKNOWN),
        else_=Order.governorate,
    ).label("governorate")
    rows = session.execute(
        _apply_order_filters(
            select(label, func.count(Order.id), func.coalesce(func.sum(Order.selected_order_total), 0))
            .group_by(label),
            filters,
        ).order_by(func.sum(Order.selected_order_total).desc(), label)
    ).all()
    return [{"governorate": r[0], "order_count": r[1], "sales_total": r[2]} for r in rows]


def by_customer(
    session: Session, filters: AnalyticsFilters, limit: int, offset: int, sort_by: str, descending: bool
) -> tuple[list[dict], int]:
    # Empty names are excluded: they are not meaningful customer identities.
    base = _apply_order_filters(
        select(
            Order.customer_name.label("customer_name"),
            Order.customer_type.label("customer_type"),
            Order.governorate.label("governorate"),
            func.count(Order.id).label("order_count"),
            func.sum(Order.selected_order_total).label("total_sales"),
            func.avg(Order.selected_order_total).label("average_order_value"),
            func.max(Order.created_at).label("latest_order_date"),
        ).where(func.trim(func.coalesce(Order.customer_name, "")) != ""),
        filters,
    ).group_by(Order.customer_name, Order.customer_type, Order.governorate)
    grouped = base.subquery()
    total = session.execute(select(func.count()).select_from(grouped)).scalar_one()
    column = grouped.c[sort_by]
    order_clause = column.desc() if descending else column.asc()
    rows = session.execute(select(grouped).order_by(order_clause, grouped.c.customer_name).limit(limit).offset(offset)).mappings()
    return [dict(row) for row in rows], total


def products(
    session: Session, filters: AnalyticsFilters, limit: int, offset: int, sort_by: str, descending: bool
) -> tuple[list[dict], int]:
    query = (
        select(
            OrderProduct.official_product_name.label("official_product_name"),
            func.sum(OrderProduct.quantity).label("total_quantity"),
            func.sum(OrderProduct.free_quantity).label("total_free_quantity"),
            func.count(distinct(OrderProduct.order_id)).label("order_count"),
            func.count(
                distinct(case((func.trim(func.coalesce(Order.customer_name, "")) != "", Order.customer_name)))
            ).label("unique_customer_count"),
        )
        .join(Order, Order.id == OrderProduct.order_id)
        .group_by(OrderProduct.official_product_name)
    )
    # Product filtering applies to the rows being aggregated, not merely order membership.
    product_filter = filters.product_name
    filters_without_product = AnalyticsFilters(**{**filters.__dict__, "product_name": None})
    query = _apply_order_filters(query, filters_without_product)
    if product_filter:
        query = query.where(OrderProduct.official_product_name.ilike(f"%{product_filter}%"))
    grouped = query.subquery()
    total = session.execute(select(func.count()).select_from(grouped)).scalar_one()
    column = grouped.c[sort_by]
    order_clause = column.desc() if descending else column.asc()
    rows = session.execute(
        select(grouped).order_by(order_clause, grouped.c.official_product_name).limit(limit).offset(offset)
    ).mappings()
    return [dict(row) for row in rows], total


def price_types(session: Session, filters: AnalyticsFilters) -> list[dict]:
    rows = session.execute(
        _apply_order_filters(
            select(
                Order.selected_price_type,
                func.count(Order.id),
                func.coalesce(func.sum(Order.selected_order_total), 0),
            ).group_by(Order.selected_price_type),
            filters,
        ).order_by(Order.selected_price_type)
    ).all()
    return [{"price_type": r[0], "order_count": r[1], "sales_total": r[2]} for r in rows]


def customer_types(session: Session, filters: AnalyticsFilters) -> list[dict]:
    label = case(
        (func.trim(func.coalesce(Order.customer_type, "")) == "", UNKNOWN), else_=Order.customer_type
    ).label("customer_type")
    rows = session.execute(
        _apply_order_filters(
            select(label, func.count(Order.id), func.coalesce(func.sum(Order.selected_order_total), 0)).group_by(label),
            filters,
        ).order_by(label)
    ).all()
    return [{"customer_type": r[0], "order_count": r[1], "sales_total": r[2]} for r in rows]


def email_deliveries(session: Session, filters: AnalyticsFilters) -> dict:
    row = session.execute(
        select(
            func.coalesce(func.sum(case((EmailDelivery.status == "sent", 1), else_=0)), 0),
            func.coalesce(func.sum(case((EmailDelivery.status == "failed", 1), else_=0)), 0),
            func.coalesce(func.sum(case((EmailDelivery.status == "pending", 1), else_=0)), 0),
            func.coalesce(func.sum(case((EmailDelivery.status == "sending", 1), else_=0)), 0),
            func.count(EmailDelivery.id),
            func.max(case((EmailDelivery.status == "failed", EmailDelivery.created_at))),
        ).where(EmailDelivery.order_id.in_(_filtered_order_ids(filters)))
    ).one()
    return dict(zip(("sent", "failed", "pending", "sending", "total_attempts", "latest_failure_time"), row))


def filter_options(session: Session) -> dict:
    def values(column):
        return list(
            session.execute(
                select(column)
                .where(func.trim(func.coalesce(column, "")) != "")
                .distinct()
                .order_by(column)
            ).scalars()
        )

    bounds = session.execute(select(func.min(func.date(Order.created_at)), func.max(func.date(Order.created_at)))).one()
    return {
        "governorates": values(Order.governorate),
        "customer_types": values(Order.customer_type),
        "price_types": values(Order.selected_price_type),
        "minimum_order_date": bounds[0],
        "maximum_order_date": bounds[1],
    }
