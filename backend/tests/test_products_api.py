"""HTTP-level tests for GET /api/products and POST /api/products/select.

The catalog lookup is monkeypatched to a synthetic in-memory catalog — none of these
tests touch the real backend/templates/Hikma orders.xlsx workbook.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from excel.catalog_reader import CatalogProduct, CatalogUnavailableError
from main import app
from models.matched_order_models import ProductMatchCandidate

client = TestClient(app)

CATALOG = (
    CatalogProduct(row=3, official_name="ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)"),
    CatalogProduct(row=4, official_name="VANCO 1G IV INFU VIALS (VANCOMYCIN 1G IV)"),
    CatalogProduct(row=5, official_name="VANCO 500MG IV INFU VIALS 1'S"),
)


def test_list_products_returns_full_catalog():
    with patch("api.products.get_catalog_products", return_value=CATALOG):
        response = client.get("/api/products")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert body[0] == {"row": 3, "official_name": "ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)"}


def test_list_products_search_filtering():
    with patch("api.products.get_catalog_products", return_value=CATALOG):
        response = client.get("/api/products", params={"search": "vanco"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {item["row"] for item in body} == {4, 5}


def test_list_products_search_ranks_generic_name_and_partial_brand():
    catalog = (
        CatalogProduct(
            row=3,
            official_name="ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)",
            alias="ATRACURIUM BESILATE",
        ),
        CatalogProduct(row=4, official_name="Levofloxacin Hikma 500MG/100ML IV 1"),
    )
    with patch("api.products.get_catalog_products", return_value=catalog):
        generic = client.get("/api/products", params={"search": "atracurium"})
        partial = client.get("/api/products", params={"search": "levo"})

    assert generic.status_code == partial.status_code == 200
    assert generic.json()[0]["row"] == 3
    assert partial.json()[0]["row"] == 4


def test_list_products_search_supports_curated_arabic_aliases():
    with patch("api.products.get_catalog_products", return_value=CATALOG):
        response = client.get("/api/products", params={"search": "اتكيور"})

    assert response.status_code == 200
    assert response.json()[0]["row"] == 3


def test_list_products_handles_unavailable_catalog_safely():
    with patch(
        "api.products.get_catalog_products",
        side_effect=CatalogUnavailableError("The product catalog file could not be found."),
    ):
        response = client.get("/api/products")

    assert response.status_code == 503
    assert response.json()["detail"] == "The product catalog is currently unavailable."
    assert "Traceback" not in response.text
    assert "/Users/" not in response.text
    assert ".xlsx" not in response.text


def test_select_product_validates_against_catalog():
    expected = ProductMatchCandidate(official_name="VANCO 500MG IV INFU VIALS 1'S", row=5, score=1.0)

    with patch("api.products.validate_manual_selection", return_value=expected) as mock_validate:
        response = client.post(
            "/api/products/select",
            json={"row": 5, "official_name": "VANCO 500MG IV INFU VIALS 1'S"},
        )

    assert response.status_code == 200
    assert response.json() == {"official_name": "VANCO 500MG IV INFU VIALS 1'S", "row": 5, "score": 1.0}
    mock_validate.assert_called_once_with(5, "VANCO 500MG IV INFU VIALS 1'S")


def test_select_product_rejects_invalid_selection_with_safe_error():
    from services.product_matching_service import InvalidProductSelectionError

    with patch(
        "api.products.validate_manual_selection",
        side_effect=InvalidProductSelectionError("The selected row does not exist in the current product catalog."),
    ):
        response = client.post("/api/products/select", json={"row": 999, "official_name": "Anything"})

    assert response.status_code == 422
    assert response.json()["detail"] == "The selected row does not exist in the current product catalog."
