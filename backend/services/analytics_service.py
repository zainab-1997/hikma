"""Read-only analytics orchestration and consistent numeric rounding."""

from database.repositories import analytics_repository as repository
from database.repositories.analytics_repository import AnalyticsFilters
from database.session import session_scope
from models.analytics_models import (
    CustomerAnalytics,
    CustomerAnalyticsResponse,
    CustomerTypeAnalytics,
    EmailDeliveryAnalytics,
    FilterOptions,
    GovernorateAnalytics,
    OverviewAnalytics,
    PriceTypeAnalytics,
    ProductAnalytics,
    ProductAnalyticsResponse,
    SalesPeriod,
)


def _percentage(value: int, total: int) -> float:
    return round(value * 100 / total, 2) if total else 0.0


def get_overview(filters: AnalyticsFilters) -> OverviewAnalytics:
    with session_scope() as session:
        data = repository.overview(session, filters)
    data["average_order_value"] = round(float(data["average_order_value"]), 2)
    return OverviewAnalytics(**data)


def get_sales_over_time(filters: AnalyticsFilters, granularity: str) -> list[SalesPeriod]:
    with session_scope() as session:
        return [SalesPeriod(**row) for row in repository.sales_over_time(session, filters, granularity)]


def get_by_governorate(filters: AnalyticsFilters) -> list[GovernorateAnalytics]:
    with session_scope() as session:
        rows = repository.by_governorate(session, filters)
    total = sum(row["sales_total"] for row in rows)
    return [GovernorateAnalytics(**row, percentage_of_total_sales=_percentage(row["sales_total"], total)) for row in rows]


def get_by_customer(filters, limit, offset, sort_by, descending) -> CustomerAnalyticsResponse:
    with session_scope() as session:
        rows, total = repository.by_customer(session, filters, limit, offset, sort_by, descending)
    items = [
        CustomerAnalytics(**{**row, "average_order_value": round(float(row["average_order_value"]), 2)})
        for row in rows
    ]
    return CustomerAnalyticsResponse(items=items, total=total, limit=limit, offset=offset)


def get_products(filters, limit, offset, sort_by, descending) -> ProductAnalyticsResponse:
    with session_scope() as session:
        rows, total = repository.products(session, filters, limit, offset, sort_by, descending)
    return ProductAnalyticsResponse(
        items=[ProductAnalytics(**row) for row in rows], total=total, limit=limit, offset=offset
    )


def get_price_types(filters: AnalyticsFilters) -> list[PriceTypeAnalytics]:
    with session_scope() as session:
        rows = repository.price_types(session, filters)
    total = sum(row["sales_total"] for row in rows)
    return [PriceTypeAnalytics(**row, percentage_of_total_sales=_percentage(row["sales_total"], total)) for row in rows]


def get_customer_types(filters: AnalyticsFilters) -> list[CustomerTypeAnalytics]:
    with session_scope() as session:
        return [CustomerTypeAnalytics(**row) for row in repository.customer_types(session, filters)]


def get_email_deliveries(filters: AnalyticsFilters) -> EmailDeliveryAnalytics:
    with session_scope() as session:
        data = repository.email_deliveries(session, filters)
    data["success_rate"] = _percentage(data["sent"], data["total_attempts"])
    return EmailDeliveryAnalytics(**data)


def get_filter_options() -> FilterOptions:
    with session_scope() as session:
        return FilterOptions(**repository.filter_options(session))
