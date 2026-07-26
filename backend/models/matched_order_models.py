"""Pydantic models for the deterministic product-matching layer."""

from typing import Literal

from pydantic import BaseModel, Field

from models.review_order_models import ReviewOrderResponse

MatchStatus = Literal["matched", "fuzzy", "ambiguous", "strength_conflict", "unmatched"]


class ProductMatchCandidate(BaseModel):
    official_name: str
    row: int
    score: float = Field(..., ge=0, le=1)


class MatchedProductData(BaseModel):
    written_product_name: str
    quantity: int
    free_quantity: int = 0
    free_percentage: float | None = None
    expiry_date: str | None = None
    notes: str | None = None

    match_status: MatchStatus
    matched_official_name: str | None = None
    matched_row: int | None = None
    match_score: float | None = Field(default=None, ge=0, le=1)
    candidates: list[ProductMatchCandidate] = Field(default_factory=list)


class MatchedOrderResponse(ReviewOrderResponse):
    products: list[MatchedProductData] = Field(default_factory=list)
    all_products_matched: bool


class CatalogProductItem(BaseModel):
    row: int
    official_name: str


class ProductSelectionRequest(BaseModel):
    row: int
    official_name: str = Field(..., min_length=1)
