"""Read-only access to the official product catalog inside the company Excel template.

This module only ever opens a workbook for reading (`read_only=True`) and never calls
`save()`. The template is the company's authoritative order file and must never be
modified by this layer.

Verified workbook structure (backend/templates/Hikma orders.xlsx):
- Worksheet: Sheet1
- Header row: 2
- Product name column: A
- Product rows: 3 through 14 (row 15 is a totals row and is never treated as a product)

The catalog is cached per (file path, file modification time), so unchanged files are
never re-read, and edited files (a changed mtime) are picked up on the next call without
needing a process restart.
"""

import os
import re
import hashlib
from dataclasses import dataclass

import openpyxl

from config.settings import get_settings

WORKSHEET_NAME = "Sheet1"
PRODUCT_NAME_COLUMN = "A"
HEADER_ROW = 2
FIRST_PRODUCT_ROW = 3
LAST_PRODUCT_ROW = 14

_ALIAS_PATTERN = re.compile(r"\(([^)]+)\)")


class CatalogUnavailableError(Exception):
    """Raised when the product catalog workbook cannot be read.

    The message is always a safe, generic description — never a raw filesystem path or
    the underlying library's stack trace — since it may end up in an API error response.
    """


@dataclass(frozen=True)
class CatalogProduct:
    row: int
    official_name: str
    alias: str | None = None
    drug_store_price: float | None = None
    pharmacy_price: float | None = None


def _extract_alias(official_name: str) -> str | None:
    """Pull the parenthesized generic/alternate name out of an official product name.

    e.g. "ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)" -> "ATRACURIUM BESILATE"
    """
    match = _ALIAS_PATTERN.search(official_name)
    if not match:
        return None
    alias = match.group(1).strip()
    return alias or None


def _read_catalog_products(template_path: str) -> list[CatalogProduct]:
    try:
        workbook = openpyxl.load_workbook(template_path, read_only=True, data_only=True)
    except FileNotFoundError as exc:
        raise CatalogUnavailableError("The product catalog file could not be found.") from exc
    except Exception as exc:
        raise CatalogUnavailableError("The product catalog file could not be opened.") from exc

    try:
        if WORKSHEET_NAME not in workbook.sheetnames:
            raise CatalogUnavailableError(
                f'The product catalog is missing the expected "{WORKSHEET_NAME}" worksheet.'
            )

        worksheet = workbook[WORKSHEET_NAME]
        products: list[CatalogProduct] = []
        for row in range(FIRST_PRODUCT_ROW, LAST_PRODUCT_ROW + 1):
            value = worksheet[f"{PRODUCT_NAME_COLUMN}{row}"].value
            name = str(value).strip() if value is not None else ""
            if name:
                drug_store_price = worksheet[f"B{row}"].value
                pharmacy_price = worksheet[f"C{row}"].value
                products.append(
                    CatalogProduct(
                        row=row,
                        official_name=name,
                        alias=_extract_alias(name),
                        drug_store_price=(
                            float(drug_store_price)
                            if isinstance(drug_store_price, (int, float))
                            else None
                        ),
                        pharmacy_price=(
                            float(pharmacy_price)
                            if isinstance(pharmacy_price, (int, float))
                            else None
                        ),
                    )
                )
        return products
    finally:
        workbook.close()


_catalog_cache: dict[tuple[str, int, int], tuple[CatalogProduct, ...]] = {}


def get_catalog_products(template_path: str | None = None) -> tuple[CatalogProduct, ...]:
    """Load the official product catalog, cached by (path, mtime).

    Pass template_path explicitly in tests to use a temporary workbook instead of the
    real, settings-configured Hikma template.
    """
    path = template_path if template_path is not None else get_settings().excel_template_path

    try:
        stat = os.stat(path)
    except OSError as exc:
        raise CatalogUnavailableError("The product catalog file could not be found.") from exc

    canonical_path = os.path.realpath(path)
    cache_key = (canonical_path, stat.st_mtime_ns, stat.st_size)
    if cache_key not in _catalog_cache:
        _catalog_cache.clear()
        _catalog_cache[cache_key] = tuple(_read_catalog_products(canonical_path))

    return _catalog_cache[cache_key]


def catalog_version(catalog: tuple[CatalogProduct, ...]) -> str:
    payload = "\n".join(f"{item.row}:{item.official_name}" for item in catalog)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clear_catalog_cache() -> None:
    _catalog_cache.clear()


def find_duplicate_official_names(catalog: tuple[CatalogProduct, ...]) -> list[str]:
    """Return official names (data-quality issue) that appear on more than one catalog row."""
    seen: dict[str, int] = {}
    for product in catalog:
        key = product.official_name.strip().lower()
        seen[key] = seen.get(key, 0) + 1

    duplicates = {key for key, count in seen.items() if count > 1}
    return sorted(
        {product.official_name for product in catalog if product.official_name.strip().lower() in duplicates}
    )
