"""Pydantic models for the deterministic business-rules layer."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from models.order_models import CustomerData, ParsedOrderResponse, ProductData, TransitData

PriceType = Literal["pharmacy", "drug_store", "unknown"]


class ApplyRulesRequest(ParsedOrderResponse):
    """Input to the business-rules engine: a parsed order plus optional user confirmations.

    price_type_override lets the frontend resolve an office-customer pricing confirmation
    (Pharmacy Price vs Drug Store Price) without the engine ever guessing it on its own.
    """

    price_type_override: PriceType | None = None


class RuleWarning(BaseModel):
    type: str
    message: str
    details: dict[str, Any] | None = None


class RuleConfirmation(RuleWarning):
    """Same shape as a warning: a type, a human-readable message, and optional details."""


class ReviewOrderResponse(BaseModel):
    customer: CustomerData
    transit: TransitData
    order_title: str
    price_type: PriceType
    price_type_requires_confirmation: bool
    products: list[ProductData] = Field(default_factory=list)
    order_notes: list[str] = Field(default_factory=list)
    blocking_errors: list[RuleWarning] = Field(default_factory=list)
    warnings: list[RuleWarning] = Field(default_factory=list)
    required_confirmations: list[RuleConfirmation] = Field(default_factory=list)
    informational_notices: list[RuleWarning] = Field(default_factory=list)
    # Backward-compatible list of genuinely required missing fields only.
    missing_information: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0, le=1)
    can_generate_excel: bool
    can_proceed_to_product_matching: bool
    products_require_matching: bool = True
