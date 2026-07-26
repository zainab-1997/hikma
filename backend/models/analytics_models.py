"""Explicit response models for the read-only analytics API."""

from datetime import datetime

from pydantic import BaseModel


class OverviewAnalytics(BaseModel):
    total_orders: int
    total_sales_value: int
    total_ordered_quantity: int
    total_free_quantity: int
    average_order_value: float
    unique_customers: int
    unique_governorates: int
    sent_email_count: int
    failed_email_count: int


class SalesPeriod(BaseModel):
    period: str
    order_count: int
    sales_total: int
    ordered_quantity: int
    free_quantity: int


class GovernorateAnalytics(BaseModel):
    governorate: str
    order_count: int
    sales_total: int
    percentage_of_total_sales: float


class CustomerAnalytics(BaseModel):
    customer_name: str
    customer_type: str | None
    governorate: str | None
    order_count: int
    total_sales: int
    average_order_value: float
    latest_order_date: datetime


class CustomerAnalyticsResponse(BaseModel):
    items: list[CustomerAnalytics]
    total: int
    limit: int
    offset: int


class ProductAnalytics(BaseModel):
    official_product_name: str
    total_quantity: int
    total_free_quantity: int
    order_count: int
    unique_customer_count: int


class ProductAnalyticsResponse(BaseModel):
    items: list[ProductAnalytics]
    total: int
    limit: int
    offset: int
    sales_value_available: bool = False
    sales_value_limitation: str = (
        "Historical product sales value is unavailable because product lines do not store "
        "unit price or line value."
    )


class PriceTypeAnalytics(BaseModel):
    price_type: str
    order_count: int
    sales_total: int
    percentage_of_total_sales: float


class CustomerTypeAnalytics(BaseModel):
    customer_type: str
    order_count: int
    sales_total: int


class EmailDeliveryAnalytics(BaseModel):
    sent: int
    failed: int
    pending: int
    sending: int
    total_attempts: int
    success_rate: float
    latest_failure_time: datetime | None


class FilterOptions(BaseModel):
    governorates: list[str]
    customer_types: list[str]
    price_types: list[str]
    minimum_order_date: str | None
    maximum_order_date: str | None
