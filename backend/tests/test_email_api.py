"""HTTP-level tests for the email endpoints:
POST /api/orders/{order_id}/send-email, GET /api/orders/{order_id}/emails,
GET /api/orders/{order_id}/emails/{delivery_id}, GET /api/email/config.

The email service is monkeypatched — none of these tests touch a real network
connection, the real database, or the real Hikma workbook.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.email_models import EmailDeliveryDetail, EmailDeliverySummary, SendOrderEmailResponse
from services.email_errors import (
    EmailConfigurationError,
    GeneratedFileMissingError,
    OrderNotFoundForEmailError,
    RecipientValidationError,
)

client = TestClient(app)

VALID_PAYLOAD = {
    "email_request_id": "req-1",
    "to_addresses": ["pharmacy@example.com"],
    "cc_addresses": [],
    "subject_override": None,
    "message": None,
}

SAMPLE_RESPONSE = SendOrderEmailResponse(
    success=True,
    delivery_id="delivery-1",
    order_id="order-1",
    order_number="HIK-20260725-0001",
    status="sent",
    to_addresses=["pharmacy@example.com"],
    cc_addresses=[],
    subject="Hikma Order HIK-20260725-0001 - صيدلية العين",
    sent_at=datetime(2026, 7, 25, 9, 30, tzinfo=timezone.utc),
)


def test_send_email_endpoint_returns_metadata_on_success():
    with patch("api.orders.send_order_email", return_value=SAMPLE_RESPONSE):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "sent"
    assert body["order_number"] == "HIK-20260725-0001"


def test_send_email_endpoint_reports_failed_status_as_200():
    failed_response = SAMPLE_RESPONSE.model_copy(
        update={"success": False, "status": "failed", "sent_at": None, "error_message": "The email server did not respond in time."}
    )
    with patch("api.orders.send_order_email", return_value=failed_response):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["status"] == "failed"


def test_send_email_endpoint_rejects_empty_to_addresses():
    payload = {**VALID_PAYLOAD, "to_addresses": []}
    response = client.post("/api/orders/order-1/send-email", json=payload)
    assert response.status_code == 422


def test_send_email_endpoint_does_not_accept_attachment_path_or_total():
    payload = {**VALID_PAYLOAD, "attachment_path": "/etc/passwd", "order_total": 999999999}
    with patch("api.orders.send_order_email", return_value=SAMPLE_RESPONSE) as mock_send:
        client.post("/api/orders/order-1/send-email", json=payload)

    called_request = mock_send.call_args.args[1]
    assert not hasattr(called_request, "attachment_path")
    assert not hasattr(called_request, "order_total")


def test_send_email_endpoint_maps_order_not_found_to_404():
    with patch("api.orders.send_order_email", side_effect=OrderNotFoundForEmailError("Order not found.")):
        response = client.post("/api/orders/does-not-exist/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


def test_send_email_endpoint_maps_missing_file_to_404():
    with patch(
        "api.orders.send_order_email",
        side_effect=GeneratedFileMissingError("The generated Excel file for this order was not found."),
    ):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 404


def test_send_email_endpoint_maps_config_disabled_to_503():
    with patch("api.orders.send_order_email", side_effect=EmailConfigurationError("Email delivery is currently disabled.")):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_send_email_endpoint_maps_invalid_recipient_to_422():
    with patch("api.orders.send_order_email", side_effect=RecipientValidationError('"bad" is not a valid email address.')):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert response.status_code == 422


def test_send_email_endpoint_response_has_no_secrets_or_paths():
    with patch("api.orders.send_order_email", return_value=SAMPLE_RESPONSE):
        response = client.post("/api/orders/order-1/send-email", json=VALID_PAYLOAD)

    assert "smtp" not in response.text.lower()
    assert "/Users/" not in response.text
    assert "Traceback" not in response.text


def test_list_order_emails_endpoint_returns_newest_first():
    summaries = [
        EmailDeliverySummary(
            delivery_id="d2", order_id="order-1", attempt_number=2, status="sent",
            to_addresses=["a@example.com"], cc_addresses=[], subject="S2",
            created_at=datetime(2026, 7, 25, 10, 0, tzinfo=timezone.utc), sent_at=None, safe_error_message=None,
        ),
        EmailDeliverySummary(
            delivery_id="d1", order_id="order-1", attempt_number=1, status="failed",
            to_addresses=["a@example.com"], cc_addresses=[], subject="S1",
            created_at=datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc), sent_at=None,
            safe_error_message="The email server did not respond in time.",
        ),
    ]
    with patch("api.orders.list_email_deliveries", return_value=summaries):
        response = client.get("/api/orders/order-1/emails")

    assert response.status_code == 200
    body = response.json()
    assert [item["attempt_number"] for item in body] == [2, 1]


def test_get_order_email_detail_endpoint():
    detail = EmailDeliveryDetail(
        delivery_id="d1", order_id="order-1", attempt_number=1, status="sent",
        to_addresses=["a@example.com"], cc_addresses=[], subject="S1",
        created_at=datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc),
        sent_at=datetime(2026, 7, 25, 9, 1, tzinfo=timezone.utc),
        safe_error_message=None, optional_message="Please confirm.", error_code=None,
    )
    with patch("api.orders.get_email_delivery_detail", return_value=detail):
        response = client.get("/api/orders/order-1/emails/d1")

    assert response.status_code == 200
    assert response.json()["optional_message"] == "Please confirm."


def test_get_order_email_detail_invalid_delivery_id_returns_safe_404():
    with patch("api.orders.get_email_delivery_detail", return_value=None):
        response = client.get("/api/orders/order-1/emails/does-not-exist")

    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_email_config_endpoint_never_exposes_smtp_settings():
    response = client.get("/api/email/config")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"email_enabled", "default_recipients", "from_name"}
    assert "smtp_host" not in response.text.lower()
    assert "smtp_password" not in response.text.lower()
    assert "smtp_port" not in response.text.lower()
