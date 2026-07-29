"""Regression coverage against the authoritative workbook, not a synthetic catalog."""

import pytest
from fastapi.testclient import TestClient

from excel.catalog_reader import get_catalog_products
from main import app
from services.product_matching_service import match_single_product


def test_every_official_catalog_name_resolves_to_its_exact_workbook_row():
    catalog = get_catalog_products()
    assert catalog
    for product in catalog:
        status, official_name, row, _score, _candidates = match_single_product(
            product.official_name.swapcase(), catalog
        )
        assert status == "matched"
        assert row == product.row
        assert official_name == product.official_name


@pytest.mark.parametrize(
    ("written", "expected_row"),
    [
        ("فانكو ٥٠٠", 14),
        ("اتكيور ٥٠", 3),
        ("كلوبرام ١٠", 4),
        ("فلوران", 5),
        ("ميدازولام ١٥", 6),
        ("نيكسس ٤٠", 7),
        ("سيترون ٤", 8),
        ("تيكام ٥٠", 10),
        ("سيبرولون ٢٠٠", 11),
        ("ليفوفلوكساسين ٥٠٠", 12),
        ("vanco 0.5", 14),
        ("فانكو 500mg", 14),
    ],
)
def test_catalog_derived_cross_script_keys_resolve_representative_real_products(
    written, expected_row
):
    catalog = get_catalog_products()
    status, _official_name, row, _score, candidates = match_single_product(written, catalog)
    assert status == "matched"
    assert row == expected_row
    if expected_row == 14:
        assert all(candidate.row != 13 for candidate in candidates)


def test_real_catalog_prices_are_indexed_from_the_workbook():
    catalog = get_catalog_products()
    assert all(product.drug_store_price is not None for product in catalog)
    assert all(product.pharmacy_price is not None for product in catalog)


@pytest.mark.parametrize(("written", "expected_row"), [("فانكو ٥٠٠", 14), ("vanco 0.5", 14)])
def test_real_frontend_match_route_returns_one_safe_catalog_family_candidate(
    written, expected_row
):
    payload = {
        "customer": {"customer_name": "صيدلية العين", "customer_type": "pharmacy"},
        "transit": {"is_transit": False, "destination_type": "unknown"},
        "order_title": "صيدلية العين",
        "price_type": "pharmacy",
        "price_type_requires_confirmation": False,
        "products": [{"written_product_name": written, "quantity": None}],
        "order_notes": [],
        "blocking_errors": [
            {
                "type": "invalid_quantity",
                "message": "Quantity required.",
                "details": {"product_name": written, "field": "quantity"},
            }
        ],
        "warnings": [],
        "required_confirmations": [],
        "informational_notices": [],
        "missing_information": ["quantity"],
        "confidence_score": 0.99,
        "can_generate_excel": False,
        "can_proceed_to_product_matching": False,
        "products_require_matching": True,
    }
    response = TestClient(app).post("/api/orders/match-products", json=payload)
    assert response.status_code == 200
    product = response.json()["products"][0]
    assert product["match_status"] == "matched"
    assert product["matched_row"] == expected_row
    assert [candidate["row"] for candidate in product["candidates"]] == [expected_row]
