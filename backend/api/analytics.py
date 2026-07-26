"""Thin HTTP routes for safe, read-only analytics."""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from database.repositories.analytics_repository import AnalyticsFilters
from models.analytics_models import (
    CustomerAnalyticsResponse,
    CustomerTypeAnalytics,
    EmailDeliveryAnalytics,
    FilterOptions,
    GovernorateAnalytics,
    OverviewAnalytics,
    PriceTypeAnalytics,
    ProductAnalyticsResponse,
    SalesPeriod,
)
from services import analytics_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _filters(
    date_from: date | None,
    date_to: date | None,
    governorate: str | None,
    customer_type: str | None,
    selected_price_type: str | None,
    customer_name: str | None,
    product_name: str | None,
) -> AnalyticsFilters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")
    start = datetime.combine(date_from, time.min, timezone.utc) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc) if date_to else None
    return AnalyticsFilters(start, end, governorate, customer_type, selected_price_type, customer_name, product_name)


def _common(
    date_from: date | None = Query(None, description="Inclusive UTC date, YYYY-MM-DD"),
    date_to: date | None = Query(None, description="Inclusive UTC date, YYYY-MM-DD"),
    governorate: str | None = None,
    customer_type: str | None = None,
    selected_price_type: str | None = None,
    customer_name: str | None = None,
    product_name: str | None = None,
) -> AnalyticsFilters:
    return _filters(date_from, date_to, governorate, customer_type, selected_price_type, customer_name, product_name)


def _safe(call, *args):
    try:
        return call(*args)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Analytics query failed.")
        raise HTTPException(status_code=500, detail="Unable to load analytics.") from None


@router.get("/overview", response_model=OverviewAnalytics)
def overview(filters: AnalyticsFilters = Depends(_common)):
    return _safe(analytics_service.get_overview, filters)


@router.get("/sales-over-time", response_model=list[SalesPeriod])
def sales_over_time(
    granularity: Literal["daily", "weekly", "monthly"] = "daily",
    filters: AnalyticsFilters = Depends(_common),
):
    return _safe(analytics_service.get_sales_over_time, filters, granularity)


@router.get("/by-governorate", response_model=list[GovernorateAnalytics])
def by_governorate(filters: AnalyticsFilters = Depends(_common)):
    return _safe(analytics_service.get_by_governorate, filters)


@router.get("/by-customer", response_model=CustomerAnalyticsResponse)
def by_customer(
    filters: AnalyticsFilters = Depends(_common),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: Literal["customer_name", "order_count", "total_sales", "average_order_value", "latest_order_date"] = "total_sales",
    sort_direction: Literal["asc", "desc"] = "desc",
):
    return _safe(analytics_service.get_by_customer, filters, limit, offset, sort_by, sort_direction == "desc")


@router.get("/products", response_model=ProductAnalyticsResponse)
def products(
    filters: AnalyticsFilters = Depends(_common),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: Literal["official_product_name", "total_quantity", "total_free_quantity", "order_count", "unique_customer_count"] = "total_quantity",
    sort_direction: Literal["asc", "desc"] = "desc",
):
    return _safe(analytics_service.get_products, filters, limit, offset, sort_by, sort_direction == "desc")


@router.get("/price-types", response_model=list[PriceTypeAnalytics])
def price_types(filters: AnalyticsFilters = Depends(_common)):
    return _safe(analytics_service.get_price_types, filters)


@router.get("/customer-types", response_model=list[CustomerTypeAnalytics])
def customer_types(filters: AnalyticsFilters = Depends(_common)):
    return _safe(analytics_service.get_customer_types, filters)


@router.get("/email-deliveries", response_model=EmailDeliveryAnalytics)
def email_deliveries(filters: AnalyticsFilters = Depends(_common)):
    return _safe(analytics_service.get_email_deliveries, filters)


@router.get("/filter-options", response_model=FilterOptions)
def filter_options():
    return _safe(analytics_service.get_filter_options)
