"""Pydantic models for confirmed-order Excel generation and persistence."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from models.order_models import CustomerType

ConfirmedPriceType = Literal["pharmacy", "drug_store"]


class ConfirmedMatchedProduct(BaseModel):
    """A single order line the user has confirmed. matched_row/matched_official_name are
    always revalidated against the live catalog server-side — the frontend's word for it
    is never trusted on its own. match_status/match_score/free_percentage are carried
    through only as audit metadata for the persisted record; they don't affect validation."""

    written_product_name: str = Field(..., min_length=1)
    matched_row: int = Field(..., ge=1)
    matched_official_name: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    free_quantity: int = Field(default=0, ge=0)
    free_percentage: float | None = Field(default=None, ge=0)
    notes: str | None = None
    match_status: str | None = None
    match_score: float | None = Field(default=None, ge=0, le=1)


class GenerateOrderRequest(BaseModel):
    order_title: str = Field(..., min_length=1)
    selected_price_type: ConfirmedPriceType
    products: list[ConfirmedMatchedProduct] = Field(..., min_length=1)
    required_confirmations_resolved: bool = Field(
        ...,
        description=(
            "Asserted by the frontend after its own confirm-gating check (all business-rule "
            "confirmations resolved, no strength conflicts, etc). The backend independently "
            "revalidates product identity, quantities, and duplicate lines within this request."
        ),
    )
    order_notes: list[str] = Field(default_factory=list)

    # Persisted alongside the order for history/analytics — not used for pricing or
    # matching decisions, which were already made upstream and are re-validated here.
    customer_name: str | None = None
    customer_type: CustomerType | None = None
    governorate: str | None = None
    area: str | None = None
    phone_number: str | None = None
    is_transit: bool = False
    primary_customer: str | None = None
    destination_customer: str | None = None
    source_message: str | None = None
    parser_confidence_score: float | None = Field(default=None, ge=0, le=1)

    client_request_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional idempotency key, one per Confirm click. A retry with the "
        "same value returns the already-saved order instead of generating a duplicate.",
    )

    @model_validator(mode="after")
    def validate_required_order_identity(self):
        if self.is_transit:
            if not self.primary_customer or not self.primary_customer.strip():
                raise ValueError("primary_customer is required for a transit order")
            if not self.destination_customer or not self.destination_customer.strip():
                raise ValueError("destination_customer is required for a transit order")
        elif not self.customer_name or not self.customer_name.strip():
            raise ValueError("customer_name is required for a standard order")
        return self


class ExcelGenerationResult(BaseModel):
    """Internal result of writing the workbook — deliberately has no notion of a
    database order. services/order_persistence_service.py turns this into a
    GeneratedOrderResponse only after the order is durably saved."""

    filename: str
    download_url: str
    selected_price_type: ConfirmedPriceType
    selected_order_total: int
    excluded_order_notes: bool = Field(
        default=False,
        description="True if order_notes were provided but the template has no safe cell to hold them.",
    )


class WorkbookPreviewCell(BaseModel):
    column: int
    value: str | int | float | None = None
    formula: str | None = None
    colspan: int = Field(default=1, ge=1)
    font_bold: bool = False
    font_color: str | None = None
    fill_color: str | None = None
    horizontal_alignment: str | None = None
    number_format: str | None = None
    border_top: str | None = None
    border_right: str | None = None
    border_bottom: str | None = None
    border_left: str | None = None


class WorkbookPreviewRow(BaseModel):
    row: int
    height: float | None = None
    cells: list[WorkbookPreviewCell]


class WorkbookPreview(BaseModel):
    sheet_name: str
    rows: list[WorkbookPreviewRow]
    column_widths: list[float | None]
    max_row: int
    max_column: int
    workbook_sha256: str


class GeneratedProductSummary(BaseModel):
    entered_product: str
    official_product: str
    recognized_strength: str | None = None
    dosage_form: str | None = None
    quantity: int
    free_quantity: int
    unit_price: int
    line_total: int
    match_status: str
    warnings: list[str] = Field(default_factory=list)


class GeneratedOrderSummary(BaseModel):
    customer_name: str | None = None
    customer_type: str | None = None
    selected_price_type: ConfirmedPriceType
    order_route: str
    order_date: datetime
    order_number: str
    total_products: int
    total_ordered_quantity: int
    total_free_quantity: int
    subtotal: int
    discount: int = 0
    grand_total: int
    currency: str = "IQD"
    products: list[GeneratedProductSummary]


class GeneratedOrderResponse(BaseModel):
    success: bool = True
    order_id: str
    order_number: str
    filename: str
    download_url: str
    selected_price_type: ConfirmedPriceType
    selected_order_total: int
    created_at: datetime
    summary: GeneratedOrderSummary | None = None
    workbook_preview: WorkbookPreview | None = None
    excluded_order_notes: bool = Field(
        default=False,
        description="True if order_notes were provided but the template has no safe cell to hold them.",
    )
