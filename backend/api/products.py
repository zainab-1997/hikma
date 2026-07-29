"""HTTP routes for browsing and validating the official product catalog."""

import logging

from fastapi import APIRouter, HTTPException, Query

from excel.catalog_reader import CatalogUnavailableError, get_catalog_products
from models.matched_order_models import (
    CatalogProductItem,
    ProductMatchCandidate,
    ProductSelectionRequest,
)
from services.product_matching_service import (
    InvalidProductSelectionError,
    search_catalog_products,
    validate_manual_selection,
)
from services.approved_product_alias_service import remember_approved_alias

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[CatalogProductItem])
def list_products(
    search: str | None = Query(default=None, description="Optional search text")
) -> list[CatalogProductItem]:
    try:
        catalog = get_catalog_products()
    except CatalogUnavailableError as exc:
        logger.error("Product catalog unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="The product catalog is currently unavailable.") from exc

    results = catalog if not search else search_catalog_products(search, catalog=catalog)

    return [
        CatalogProductItem(row=product.row, official_name=product.official_name)
        for product in results
    ]


@router.post("/select", response_model=ProductMatchCandidate)
def select_product(request: ProductSelectionRequest) -> ProductMatchCandidate:
    try:
        selected = validate_manual_selection(request.row, request.official_name)
        if request.written_product_name:
            remember_approved_alias(
                request.written_product_name,
                catalog_row=selected.row,
                official_product_name=selected.official_name,
            )
        return selected
    except InvalidProductSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CatalogUnavailableError as exc:
        logger.error("Product catalog unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="The product catalog is currently unavailable.") from exc
