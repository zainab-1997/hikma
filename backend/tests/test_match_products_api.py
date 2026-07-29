"""HTTP-level tests for POST /api/orders/match-products.

The catalog lookup is monkeypatched to a synthetic in-memory catalog for every test here —
none of them touch the real backend/templates/Hikma orders.xlsx workbook.
"""

from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from excel.catalog_reader import CatalogProduct, CatalogUnavailableError
from main import app

client = TestClient(app)

CATALOG = (
    CatalogProduct(row=8, official_name="TEKAM 50MG 10ML (KETAMINE)", alias="KETAMINE"),
)

BASE_PAYLOAD = {
    "customer": {
        "customer_name": "صيدلية العين",
        "customer_type": "pharmacy",
        "governorate": "النجف",
        "area": None,
        "phone_number": None,
    },
    "transit": {
        "is_transit": False,
        "primary_customer": None,
        "destination_customer": None,
        "destination_type": "unknown",
    },
    "order_title": "صيدلية العين - النجف",
    "price_type": "pharmacy",
    "price_type_requires_confirmation": False,
    "products": [
        {
            "written_product_name": "TEKAM 50MG 10ML (KETAMINE)",
            "quantity": 5,
            "free_quantity": 0,
            "free_percentage": None,
            "expiry_date": None,
            "notes": None,
        }
    ],
    "order_notes": [],
    "warnings": [],
    "required_confirmations": [],
    "missing_information": [],
    "confidence_score": 0.9,
    "can_generate_excel": False,
    "can_proceed_to_product_matching": True,
    "products_require_matching": True,
}


def test_match_products_endpoint_returns_matched_order():
    with patch("services.product_matching_service.get_catalog_products", return_value=CATALOG):
        response = client.post("/api/orders/match-products", json=BASE_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["products"][0]["match_status"] == "matched"
    assert body["products"][0]["matched_row"] == 8
    assert body["all_products_matched"] is True
    assert body["can_generate_excel"] is False
    assert body["products_require_matching"] is False


STRENGTH_CATALOG = (
    CatalogProduct(row=20, official_name="PRODUCT 500MG TABLET"),
    CatalogProduct(row=21, official_name="PRODUCT 1G TABLET"),
    CatalogProduct(row=30, official_name="منتج 500MG TABLET"),
    CatalogProduct(row=31, official_name="منتج 1G TABLET"),
)


@pytest.mark.parametrize(
    ("written_name", "expected_row"),
    [
        ("Product 0.5", 20),
        ("Product 500", 20),
        ("Product 0.5g", 20),
        ("Product 500mg", 20),
        ("Product 1", 21),
        ("Product 1000", 21),
        ("Product 1g", 21),
        ("Product 1000mg", 21),
        ("منتج ٠.٥", 30),
        ("منتج ٥٠٠", 30),
        ("منتج نص غرام", 30),
        ("منتج ٥٠٠ ملغم", 30),
        ("منتج ١", 31),
        ("منتج ١٠٠٠", 31),
        ("منتج ١ غرام", 31),
        ("منتج ١٠٠٠ ملغم", 31),
        ("Product ٠.٥", 20),
        ("Product ٥٠٠", 20),
        ("منتج 0.5g", 30),
        ("منتج 500mg", 30),
        ("Product ٥٠٠ ملغم", 20),
        ("Product 500 x 20", 20),
        ("Product 500 qty 20", 20),
        ("منتج ٥٠٠ عدد ٢٠", 30),
    ],
)
def test_match_products_endpoint_auto_selects_normalized_unique_strength(
    written_name, expected_row
):
    payload = deepcopy(BASE_PAYLOAD)
    payload["products"][0]["written_product_name"] = written_name

    with patch(
        "services.product_matching_service.get_catalog_products",
        return_value=STRENGTH_CATALOG,
    ):
        response = client.post("/api/orders/match-products", json=payload)

    assert response.status_code == 200
    body = response.json()
    product = body["products"][0]
    expected = next(item for item in STRENGTH_CATALOG if item.row == expected_row)
    assert product["match_status"] == "matched"
    assert product["matched_row"] == expected_row
    assert product["matched_official_name"] == expected.official_name
    assert [candidate["row"] for candidate in product["candidates"]] == [expected_row]
    assert body["all_products_matched"] is True
    assert body["products_require_matching"] is False


@pytest.mark.parametrize("written_name", ["Product", "منتج"])
def test_match_products_endpoint_preserves_review_when_strength_is_omitted(written_name):
    payload = deepcopy(BASE_PAYLOAD)
    payload["products"][0]["written_product_name"] = written_name

    with patch(
        "services.product_matching_service.get_catalog_products",
        return_value=STRENGTH_CATALOG,
    ):
        response = client.post("/api/orders/match-products", json=payload)

    assert response.status_code == 200
    product = response.json()["products"][0]
    assert product["match_status"] == "ambiguous"
    assert product["matched_row"] is None
    assert len(product["candidates"]) == 2
    assert response.json()["all_products_matched"] is False


def test_match_products_endpoint_does_not_infer_when_unit_interpretations_conflict():
    catalog = (
        CatalogProduct(row=40, official_name="PRODUCT 1MG TABLET"),
        CatalogProduct(row=41, official_name="PRODUCT 1G TABLET"),
    )
    payload = deepcopy(BASE_PAYLOAD)
    payload["products"][0]["written_product_name"] = "Product 1"

    with patch(
        "services.product_matching_service.get_catalog_products",
        return_value=catalog,
    ):
        response = client.post("/api/orders/match-products", json=payload)

    assert response.status_code == 200
    product = response.json()["products"][0]
    assert product["match_status"] == "ambiguous"
    assert product["matched_row"] is None
    assert {candidate["row"] for candidate in product["candidates"]} == {40, 41}
    assert response.json()["all_products_matched"] is False


def test_match_products_endpoint_handles_unavailable_catalog_safely():
    with patch(
        "services.product_matching_service.get_catalog_products",
        side_effect=CatalogUnavailableError("The product catalog file could not be found."),
    ):
        response = client.post("/api/orders/match-products", json=BASE_PAYLOAD)

    assert response.status_code == 503
    body = response.json()
    assert body["detail"] == "The product catalog is currently unavailable."
    # No internal file paths or stack traces leak into the response.
    assert "Traceback" not in response.text
    assert "/Users/" not in response.text
    assert ".xlsx" not in response.text
