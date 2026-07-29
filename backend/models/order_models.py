"""Pydantic models for the WhatsApp order parsing API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CustomerType = Literal["pharmacy", "hospital", "drug_store", "office", "unknown"]


class ParseOrderRequest(BaseModel):
    message: str = Field(..., min_length=1)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty")
        return value


class CustomerData(BaseModel):
    customer_name: str | None = None
    customer_type: CustomerType = "unknown"
    governorate: str | None = None
    area: str | None = None
    phone_number: str | None = None


class TransitData(BaseModel):
    is_transit: bool = False
    primary_customer: str | None = None
    destination_customer: str | None = None
    destination_type: CustomerType = "unknown"


class ProductData(BaseModel):
    written_product_name: str
    strength: str | None = None
    concentration: str | None = None
    dosage_form: str | None = None
    package_size: str | None = None
    quantity: int | None = Field(default=None, ge=0, le=1_000_000)
    free_quantity: int = Field(default=0, ge=0, le=1_000_000)
    free_percentage: float | None = Field(default=None, ge=0)
    expiry_date: str | None = None
    notes: str | None = None


class ParsedOrderResponse(BaseModel):
    customer: CustomerData
    transit: TransitData
    products: list[ProductData] = Field(default_factory=list)
    order_notes: list[str] = Field(default_factory=list)
    mentioned_people: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0, le=1)
