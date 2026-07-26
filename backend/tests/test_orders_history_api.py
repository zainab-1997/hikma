"""HTTP-level tests for the read-only order history endpoints:
GET /api/orders, GET /api/orders/{order_id}, GET /api/orders/{order_id}/download.

The persistence service is monkeypatched — none of these tests touch the real
backend/database/app.db or backend/templates/Hikma orders.xlsx.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.order_history_models import OrderDetail, OrderListResponse, OrderProductDetail, OrderSummary

client = TestClient(app)

SAMPLE_SUMMARY = OrderSummary(
    order_id="order-1",
    order_number="HIK-20260725-0001",
    customer_name="صيدلية العين",
    customer_type="pharmacy",
    governorate="النجف",
    selected_price_type="pharmacy",
    selected_order_total=6000,
    created_at=datetime(2026, 7, 25, 14, 30, 15, tzinfo=timezone.utc),
    download_url="/api/orders/download/order.xlsx",
    email_status=None,
    last_email_sent_at=None,
)

SAMPLE_DETAIL = OrderDetail(
    order_id="order-1",
    order_number="HIK-20260725-0001",
    customer_name="صيدلية العين",
    customer_type="pharmacy",
    governorate="النجف",
    area=None,
    phone_number=None,
    order_title="صيدلية العين - النجف",
    is_transit=False,
    primary_customer=None,
    destination_customer=None,
    selected_price_type="pharmacy",
    selected_order_total=6000,
    generated_filename="order.xlsx",
    download_url="/api/orders/download/order.xlsx",
    created_at=datetime(2026, 7, 25, 14, 30, 15, tzinfo=timezone.utc),
    email_status=None,
    last_email_sent_at=None,
    products=[
        OrderProductDetail(
            written_product_name="فانكو 500",
            official_product_name="VANCO 500MG IV INFU VIALS 1's",
            row_number=14,
            quantity=50,
            free_quantity=0,
            free_percentage=None,
            product_note=None,
            match_status="matched",
            match_score=1.0,
        )
    ],
)


def test_list_orders_endpoint_returns_summaries():
    fake_response = OrderListResponse(orders=[SAMPLE_SUMMARY], total=1, limit=50, offset=0)

    with patch("api.orders.list_order_summaries", return_value=fake_response) as mock_list:
        response = client.get("/api/orders")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["orders"][0]["order_number"] == "HIK-20260725-0001"
    mock_list.assert_called_once()


def test_list_orders_endpoint_forwards_filters_and_pagination():
    fake_response = OrderListResponse(orders=[], total=0, limit=10, offset=5)

    with patch("api.orders.list_order_summaries", return_value=fake_response) as mock_list:
        response = client.get(
            "/api/orders",
            params={
                "governorate": "النجف",
                "customer_name": "صيدلية",
                "price_type": "pharmacy",
                "limit": 10,
                "offset": 5,
            },
        )

    assert response.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["governorate"] == "النجف"
    assert kwargs["customer_name"] == "صيدلية"
    assert kwargs["price_type"] == "pharmacy"
    assert kwargs["limit"] == 10
    assert kwargs["offset"] == 5


def test_list_orders_endpoint_rejects_invalid_date_filter():
    response = client.get("/api/orders", params={"date_from": "not-a-date"})
    assert response.status_code == 422


def test_get_order_detail_returns_full_order_with_products():
    with patch("api.orders.get_order_detail", return_value=SAMPLE_DETAIL):
        response = client.get("/api/orders/order-1")

    assert response.status_code == 200
    body = response.json()
    assert body["order_number"] == "HIK-20260725-0001"
    assert len(body["products"]) == 1
    assert body["products"][0]["official_product_name"] == "VANCO 500MG IV INFU VIALS 1's"
    # No internal filesystem paths leak into the response.
    assert "/Users/" not in response.text
    assert "generated_orders" not in response.text


def test_get_order_detail_invalid_id_returns_safe_404():
    with patch("api.orders.get_order_detail", return_value=None):
        response = client.get("/api/orders/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."
    assert "Traceback" not in response.text


def test_historical_download_serves_the_file(tmp_path):
    fake_file = tmp_path / "order.xlsx"
    fake_file.write_bytes(b"PK\x03\x04fake xlsx bytes")

    with patch("api.orders.get_order_generated_file_id", return_value="order.xlsx"):
        with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
            response = client.get("/api/orders/order-1/download")

    assert response.status_code == 200
    assert response.content == b"PK\x03\x04fake xlsx bytes"


def test_historical_download_missing_order_returns_safe_404():
    with patch("api.orders.get_order_generated_file_id", return_value=None):
        response = client.get("/api/orders/does-not-exist/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


def test_historical_download_missing_file_on_disk_returns_safe_404(tmp_path):
    with patch("api.orders.get_order_generated_file_id", return_value="missing.xlsx"):
        with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
            response = client.get("/api/orders/order-1/download")

    assert response.status_code == 404
    assert "Traceback" not in response.text
    assert str(tmp_path) not in response.text
