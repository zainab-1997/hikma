"""Pydantic models for emailing an already-generated, saved order.

The request deliberately carries no attachment path, filename, workbook path, or order
total — all order metadata and the attachment's identity come exclusively from the saved
database Order, resolved server-side. Nothing here lets a caller send an arbitrary file
or claim an arbitrary total.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EmailDeliveryStatus = Literal["pending", "sending", "sent", "failed"]


class SendOrderEmailRequest(BaseModel):
    email_request_id: str = Field(..., min_length=1, max_length=64)
    to_addresses: list[str] = Field(..., min_length=1)
    cc_addresses: list[str] = Field(default_factory=list)
    subject_override: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=2000)


class SendOrderEmailResponse(BaseModel):
    success: bool
    delivery_id: str
    order_id: str
    order_number: str
    status: EmailDeliveryStatus
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    sent_at: datetime | None = None
    error_message: str | None = None


class EmailDeliverySummary(BaseModel):
    delivery_id: str
    order_id: str
    attempt_number: int
    status: EmailDeliveryStatus
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    created_at: datetime
    sent_at: datetime | None
    safe_error_message: str | None


class EmailDeliveryDetail(EmailDeliverySummary):
    optional_message: str | None
    error_code: str | None


class EmailConfigResponse(BaseModel):
    email_enabled: bool
    default_recipients: list[str]
    from_name: str
