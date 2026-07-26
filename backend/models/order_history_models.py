"""Pydantic response models for the read-only order history endpoints."""

from datetime import datetime

from pydantic import BaseModel


class OrderSummary(BaseModel):
    order_id: str
    order_number: str
    customer_name: str | None
    customer_type: str | None
    governorate: str | None
    selected_price_type: str
    selected_order_total: int
    created_at: datetime
    download_url: str
    email_status: str | None
    last_email_sent_at: datetime | None


class OrderListResponse(BaseModel):
    orders: list[OrderSummary]
    total: int
    limit: int
    offset: int


class OrderProductDetail(BaseModel):
    written_product_name: str
    official_product_name: str
    row_number: int
    quantity: int
    free_quantity: int
    free_percentage: float | None
    product_note: str | None
    match_status: str | None
    match_score: float | None


class OrderDetail(BaseModel):
    order_id: str
    order_number: str
    customer_name: str | None
    customer_type: str | None
    governorate: str | None
    area: str | None
    phone_number: str | None
    order_title: str
    is_transit: bool
    primary_customer: str | None
    destination_customer: str | None
    selected_price_type: str
    selected_order_total: int
    generated_filename: str
    download_url: str
    created_at: datetime
    email_status: str | None
    last_email_sent_at: datetime | None
    products: list[OrderProductDetail]
