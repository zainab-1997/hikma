"""Tests for the WhatsApp order parsing endpoint and its validation rules.

The OpenAI call is always mocked — these tests never hit the real API.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from models.order_models import (
    CustomerData,
    ParsedOrderResponse,
    ProductData,
    TransitData,
)
from services.ai_parser_service import OrderParsingError

client = TestClient(app)

VALID_MESSAGE = "صيدلية العين\nفانكو ٥٠\nاتكيور ٢٠\nميدازولام ١٠"


def _sample_parsed_response() -> ParsedOrderResponse:
    return ParsedOrderResponse(
        customer=CustomerData(customer_name="صيدلية العين", customer_type="pharmacy"),
        transit=TransitData(),
        products=[
            ProductData(written_product_name="فانكو", quantity=50),
            ProductData(written_product_name="اتكيور", quantity=20),
            ProductData(written_product_name="ميدازولام", quantity=10),
        ],
        order_notes=[],
        mentioned_people=[],
        missing_information=["governorate is missing"],
        confidence_score=0.95,
    )


def test_empty_message_rejected():
    response = client.post("/api/orders/parse", json={"message": "   "})
    assert response.status_code == 422


def test_valid_request_returns_parsed_order():
    with patch("api.orders.parse_whatsapp_order", return_value=_sample_parsed_response()):
        response = client.post("/api/orders/parse", json={"message": VALID_MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["customer_name"] == "صيدلية العين"
    assert body["customer"]["customer_type"] == "pharmacy"
    assert len(body["products"]) == 3
    assert body["products"][0]["quantity"] == 50
    assert body["missing_information"] == ["governorate is missing"]


def test_invalid_customer_type_rejected():
    with pytest.raises(ValidationError):
        CustomerData(customer_name="X", customer_type="wholesaler")


def test_negative_quantity_rejected():
    with pytest.raises(ValidationError):
        ProductData(written_product_name="فانكو", quantity=-5)


def test_negative_free_quantity_rejected():
    with pytest.raises(ValidationError):
        ProductData(written_product_name="فانكو", quantity=10, free_quantity=-1)


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_confidence_score_out_of_range_rejected(score):
    with pytest.raises(ValidationError):
        ParsedOrderResponse(
            customer=CustomerData(),
            transit=TransitData(),
            products=[],
            confidence_score=score,
        )


def test_parser_service_failure_handled_safely():
    with patch(
        "api.orders.parse_whatsapp_order",
        side_effect=OrderParsingError("The AI parsing service failed to respond."),
    ):
        response = client.post("/api/orders/parse", json={"message": VALID_MESSAGE})

    assert response.status_code == 502
    assert "sk-" not in response.text
    assert "OPENAI_API_KEY" not in response.text
    assert response.json()["detail"] == "The AI parsing service failed to respond."
