"""Safe learned-alias layer backed by SQLite, never by the source workbook."""

import logging

from database.repositories.product_alias_repository import (
    find_approved_alias,
    save_approved_alias,
)
from utils.text_normalize import normalize_product_text

logger = logging.getLogger(__name__)


def get_approved_alias_row(written_product_name: str) -> int | None:
    normalized = normalize_product_text(written_product_name)
    if not normalized:
        return None
    try:
        alias = find_approved_alias(normalized)
    except Exception:
        # Matching remains available if alias persistence is temporarily unavailable.
        logger.debug("Approved product alias lookup unavailable", exc_info=True)
        return None
    return alias.catalog_row if alias is not None else None


def remember_approved_alias(
    written_product_name: str,
    *,
    catalog_row: int,
    official_product_name: str,
) -> None:
    normalized = normalize_product_text(written_product_name)
    if not normalized:
        return
    save_approved_alias(
        normalized_alias=normalized,
        written_alias=written_product_name.strip(),
        catalog_row=catalog_row,
        official_product_name=official_product_name,
    )
