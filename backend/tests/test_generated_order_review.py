import hashlib

from models.generate_order_models import ConfirmedMatchedProduct
from services.order_persistence_service import generate_and_persist_order
from tests.test_order_persistence_service import CATALOG, _file_hash, _request, _setup


def test_summary_contains_every_approved_product_and_workbook_totals(tmp_path):
    url, source, output_dir = _setup(tmp_path)
    request = _request(
        products=[
            ConfirmedMatchedProduct(
                written_product_name="Alpha 50mg",
                matched_row=3,
                matched_official_name="Alpha Tablet 50MG",
                quantity=2,
                free_quantity=1,
                match_status="matched",
            ),
            ConfirmedMatchedProduct(
                written_product_name="Beta",
                matched_row=4,
                matched_official_name="Beta Syrup",
                quantity=3,
                free_quantity=2,
                match_status="manual",
            ),
        ]
    )
    response = generate_and_persist_order(
        request,
        database_url=url,
        catalog=CATALOG,
        source_path=source,
        output_dir=output_dir,
    )

    assert response.summary is not None
    assert response.workbook_preview is not None
    assert [product.official_product for product in response.summary.products] == [
        "Alpha Tablet 50MG",
        "Beta Syrup",
    ]
    assert response.summary.total_products == 2
    assert response.summary.total_ordered_quantity == 5
    assert response.summary.total_free_quantity == 3
    assert response.summary.subtotal == 2 * 1200 + 3 * 2400
    assert response.summary.grand_total == response.selected_order_total
    assert response.summary.products[1].match_status == "manual"


def test_preview_is_a_projection_of_the_downloaded_workbook_bytes(tmp_path):
    url, source, output_dir = _setup(tmp_path)
    source_hash = _file_hash(source)
    response = generate_and_persist_order(
        _request(),
        database_url=url,
        catalog=CATALOG,
        source_path=source,
        output_dir=output_dir,
    )
    generated_path = output_dir / response.filename

    assert response.workbook_preview is not None
    assert response.workbook_preview.workbook_sha256 == hashlib.sha256(
        generated_path.read_bytes()
    ).hexdigest()
    assert response.workbook_preview.max_column == 6
    assert response.workbook_preview.rows[-1].cells[4].value == response.selected_order_total
    assert _file_hash(source) == source_hash


def test_preview_changes_after_quantity_and_manual_selection_changes(tmp_path):
    url, source, output_dir = _setup(tmp_path)
    initial = generate_and_persist_order(
        _request(products=[
            ConfirmedMatchedProduct(
                written_product_name="Alpha",
                matched_row=3,
                matched_official_name="Alpha Tablet 50MG",
                quantity=1,
                match_status="matched",
            )
        ]),
        database_url=url,
        catalog=CATALOG,
        source_path=source,
        output_dir=output_dir,
    )
    updated = generate_and_persist_order(
        _request(products=[
            ConfirmedMatchedProduct(
                written_product_name="Beta manually selected",
                matched_row=4,
                matched_official_name="Beta Syrup",
                quantity=4,
                match_status="manual",
            )
        ]),
        database_url=url,
        catalog=CATALOG,
        source_path=source,
        output_dir=output_dir,
    )

    assert initial.workbook_preview.workbook_sha256 != updated.workbook_preview.workbook_sha256
    assert updated.summary.products[0].official_product == "Beta Syrup"
    assert updated.summary.products[0].quantity == 4
    assert updated.summary.products[0].match_status == "manual"
    assert updated.summary.products[0].line_total == 4 * 2400
