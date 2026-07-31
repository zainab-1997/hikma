"""Validates a confirmed order against the live catalog and orchestrates writing it into
a fresh copy of the company Excel template. No AI is used — every check here is
deterministic. See excel/order_writer.py for the actual cell-writing logic and the
source-workbook safety model.
"""

import re
import os
from datetime import date
from pathlib import Path

from config.settings import get_settings
from excel.catalog_reader import CatalogProduct, CatalogUnavailableError, get_catalog_products
from excel.order_writer import (
    ExcelGenerationError,
    OrderLine,
    build_output_filename,
    generate_order_workbook,
)
from models.generate_order_models import ExcelGenerationResult, GenerateOrderRequest
from utils.route_format import build_order_title

GENERATED_ORDERS_DIR = Path(get_settings().generated_orders_dir)

_SAFE_GENERATED_FILENAME = re.compile(r"^[^\\/\x00-\x1f]+\.xlsx$")


def standardize_order_request(
    request: GenerateOrderRequest,
) -> GenerateOrderRequest:
    """Replace every client-supplied title with the canonical server-side title."""
    if not request.is_transit:
        customer = (request.customer_name or request.order_title).strip()
        return request.model_copy(update={"order_title": build_order_title(
            source_location=customer,
            is_transit=False,
            governorate=request.governorate,
            area=request.area,
        )})
    return request.model_copy(
        update={
            "order_title": build_order_title(
                source_location=request.primary_customer,
                is_transit=True,
                destination_customer=request.destination_customer,
                governorate=request.destination_governorate or request.governorate,
                area=request.destination_area,
            )
        }
    )


def _validate_products_against_catalog(
    request: GenerateOrderRequest, catalog: tuple[CatalogProduct, ...]
) -> None:
    catalog_official_name_by_row = {product.row: product.official_name for product in catalog}
    valid_rows = set(catalog_official_name_by_row)

    seen_rows: set[int] = set()
    for line in request.products:
        if line.matched_row not in valid_rows:
            raise ExcelGenerationError(
                f'Product row {line.matched_row} does not exist in the current product catalog.'
            )

        official_name = catalog_official_name_by_row[line.matched_row]
        if official_name.strip() != line.matched_official_name.strip():
            raise ExcelGenerationError(
                f'Product row {line.matched_row} no longer matches "{line.matched_official_name}" '
                "in the current catalog. Please re-run product matching."
            )

        if line.matched_row in seen_rows:
            raise ExcelGenerationError(
                f'Product row {line.matched_row} ("{official_name}") is used by more than one order '
                "line. Resolve the duplicate before generating the order."
            )
        seen_rows.add(line.matched_row)


def _reserve_unique_output_path(
    order_title: str, output_dir: Path, reference_date: date | None = None
) -> tuple[str, Path]:
    """Atomically reserve a readable filename for this generated order.

    Exclusive creation prevents simultaneous submissions from selecting the same
    path. The writer immediately replaces this empty reservation with a copied
    workbook; callers remove it if generation fails.
    """
    order_date = (reference_date or date.today()).isoformat()
    collision_number: int | None = None
    while True:
        filename = build_output_filename(order_title, order_date, collision_number)
        output_path = output_dir / filename
        try:
            descriptor = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            collision_number = 2 if collision_number is None else collision_number + 1
            continue
        os.close(descriptor)
        return filename, output_path


def generate_excel_order(
    request: GenerateOrderRequest,
    *,
    catalog: tuple[CatalogProduct, ...] | None = None,
    source_path: Path | None = None,
    output_dir: Path | None = None,
    filename_date: date | None = None,
) -> ExcelGenerationResult:
    """catalog/source_path/output_dir are overridable so tests never need the real,
    settings-configured Hikma template or the real generated_orders directory."""
    request = standardize_order_request(request)
    if not request.required_confirmations_resolved:
        raise ExcelGenerationError(
            "This order still has unresolved business-rule confirmations. Resolve them before generating."
        )

    if catalog is None:
        try:
            catalog = get_catalog_products()
        except CatalogUnavailableError as exc:
            raise ExcelGenerationError("The product catalog is currently unavailable.") from exc

    _validate_products_against_catalog(request, catalog)

    output_dir = output_dir if output_dir is not None else GENERATED_ORDERS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    filename_customer = (
        request.order_title
        if request.is_transit
        else request.customer_name or request.destination_customer or request.order_title
    )
    filename, output_path = _reserve_unique_output_path(
        filename_customer, output_dir, filename_date
    )

    order_lines = [
        OrderLine(row=product.matched_row, quantity=product.quantity, free_quantity=product.free_quantity, notes=product.notes)
        for product in request.products
    ]

    try:
        result = generate_order_workbook(
            order_title=request.order_title,
            order_lines=order_lines,
            selected_price_type=request.selected_price_type,
            output_path=output_path,
            source_path=source_path,
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    return ExcelGenerationResult(
        filename=filename,
        download_url=f"/api/orders/download/{filename}",
        selected_price_type=request.selected_price_type,
        selected_order_total=result.selected_order_total,
        excluded_order_notes=bool(request.order_notes),
    )


def resolve_generated_file_path(file_id: str, *, base_dir: Path | None = None) -> Path:
    """Validate a requested download identifier and resolve it to a path inside
    base_dir (GENERATED_ORDERS_DIR by default). Raises ExcelGenerationError (mapped to
    404 by the route) for anything that isn't a bare, safe filename — no path
    separators, no traversal."""
    base_dir = base_dir if base_dir is not None else GENERATED_ORDERS_DIR

    if not file_id or ".." in file_id or "/" in file_id or "\\" in file_id:
        raise ExcelGenerationError("The requested file was not found.")

    if not _SAFE_GENERATED_FILENAME.match(file_id):
        raise ExcelGenerationError("The requested file was not found.")

    candidate = (base_dir / file_id).resolve()
    if candidate.parent != base_dir.resolve():
        raise ExcelGenerationError("The requested file was not found.")

    return candidate


def delete_generated_file(filename: str, *, base_dir: Path | None = None) -> bool:
    """Best-effort delete of a just-generated file. Used only when persistence fails
    after Excel generation already succeeded (cleanup strategy A — never leave an
    orphaned, unrecorded file behind). Returns True if a file was actually removed."""
    base_dir = base_dir if base_dir is not None else GENERATED_ORDERS_DIR
    try:
        path = resolve_generated_file_path(filename, base_dir=base_dir)
    except ExcelGenerationError:
        return False

    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        pass
    return False
