"""HTTP-level tests for POST /api/orders/generate-excel.

The persistence orchestration call is monkeypatched to avoid the real catalog/template/
database — none of these tests touch backend/templates/Hikma orders.xlsx or the real
app.db.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from excel.order_writer import ExcelGenerationError
from main import app
from models.generate_order_models import GeneratedOrderResponse

client = TestClient(app)

VALID_PAYLOAD = {
    "order_title": "صيدلية العين - النجف",
    "customer_name": "صيدلية العين",
    "selected_price_type": "pharmacy",
    "products": [
        {
            "written_product_name": "Alpha",
            "matched_row": 3,
            "matched_official_name": "Alpha Tablet 50MG",
            "quantity": 5,
            "free_quantity": 0,
            "notes": None,
        }
    ],
    "required_confirmations_resolved": True,
    "order_notes": [],
}


def test_generate_excel_endpoint_returns_metadata_on_success():
    fake_response = GeneratedOrderResponse(
        order_id="order-uuid-1",
        order_number="HIK-20260725-0001",
        filename="order_20260725_143015_a1b2c3.xlsx",
        download_url="/api/orders/download/order_20260725_143015_a1b2c3.xlsx",
        selected_price_type="pharmacy",
        selected_order_total=6000,
        created_at=datetime(2026, 7, 25, 14, 30, 15, tzinfo=timezone.utc),
        excluded_order_notes=False,
    )

    with patch("api.orders.generate_and_persist_order", return_value=fake_response):
        response = client.post("/api/orders/generate-excel", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["order_id"] == "order-uuid-1"
    assert body["order_number"] == "HIK-20260725-0001"
    assert body["filename"] == "order_20260725_143015_a1b2c3.xlsx"
    assert body["download_url"] == "/api/orders/download/order_20260725_143015_a1b2c3.xlsx"
    assert body["selected_order_total"] == 6000


def test_generate_excel_endpoint_rejects_empty_products_list():
    payload = {**VALID_PAYLOAD, "products": []}
    response = client.post("/api/orders/generate-excel", json=payload)
    assert response.status_code == 422


def test_generate_excel_endpoint_rejects_unknown_price_type():
    payload = {**VALID_PAYLOAD, "selected_price_type": "unknown"}
    response = client.post("/api/orders/generate-excel", json=payload)
    assert response.status_code == 422


def test_generate_excel_endpoint_maps_validation_error_safely():
    with patch(
        "api.orders.generate_and_persist_order",
        side_effect=ExcelGenerationError("Product row 99 does not exist in the current product catalog."),
    ):
        response = client.post("/api/orders/generate-excel", json=VALID_PAYLOAD)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Product row 99 does not exist in the current product catalog."
    assert "Traceback" not in response.text
    assert "/Users/" not in response.text


def test_generate_excel_endpoint_does_not_accept_a_raw_workbook_path():
    payload = {**VALID_PAYLOAD, "template_path": "/etc/passwd"}
    fake_response = GeneratedOrderResponse(
        order_id="order-uuid-2",
        order_number="HIK-20260725-0002",
        filename="x.xlsx",
        download_url="/api/orders/download/x.xlsx",
        selected_price_type="pharmacy",
        selected_order_total=0,
        created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    with patch("api.orders.generate_and_persist_order", return_value=fake_response) as mock_generate:
        client.post("/api/orders/generate-excel", json=payload)

    # Extra/unknown fields like a workbook path must never reach the request model.
    called_request = mock_generate.call_args.args[0]
    assert not hasattr(called_request, "template_path")
