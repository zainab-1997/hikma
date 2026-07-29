"""SQLAlchemy ORM models for persisted orders.

An Order is only ever created after its Excel file has already been generated
successfully — see services/order_persistence_service.py for that guarantee. Totals are
stored as the integer computed by the Excel generation service, never a frontend-supplied
value. Timestamps are stored in UTC.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    customer_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    governorate: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    order_title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_transit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    primary_customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_customer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    selected_price_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    selected_order_total: Mapped[int] = mapped_column(Integer, nullable=False)

    generated_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    excluded_order_notes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_message: Mapped[str | None] = mapped_column(String, nullable=True)
    parser_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="generated", nullable=False)

    # Summary-only — the full attempt history lives in EmailDelivery. These two columns
    # exist purely so Order History can show "latest email status" without a join/subquery
    # per row.
    email_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    products: Mapped[list["OrderProduct"]] = relationship(
        "OrderProduct", back_populates="order", cascade="all, delete-orphan"
    )
    email_deliveries: Mapped[list["EmailDelivery"]] = relationship(
        "EmailDelivery", back_populates="order", cascade="all, delete-orphan"
    )


class OrderProduct(Base):
    __tablename__ = "order_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False, index=True)

    written_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    worksheet_name: Mapped[str] = mapped_column(String(64), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    free_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    free_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    match_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="products")


class ApprovedProductAlias(Base):
    """A user-approved spelling mapped to an immutable catalog row/name pair."""

    __tablename__ = "approved_product_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    normalized_alias: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    written_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    catalog_row: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    official_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class EmailDelivery(Base):
    """One attempt to email a saved, already-generated order.

    Recipient lists are stored as JSON text (SQLite has no reliably native JSON column
    here) — always accessed through email_repository, never as raw strings elsewhere.
    Never stores the SMTP password, a full SMTP server response, attachment bytes, or a
    filesystem path.
    """

    __tablename__ = "email_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False, index=True)
    email_request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    to_addresses: Mapped[str] = mapped_column(String, nullable=False)
    cc_addresses: Mapped[str] = mapped_column(String, default="[]", nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    optional_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    order: Mapped["Order"] = relationship("Order", back_populates="email_deliveries")
