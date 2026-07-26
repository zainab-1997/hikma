"""HTTP-level test for POST /api/orders/apply-rules. Purely deterministic — no OpenAI involved."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_apply_rules_endpoint_returns_review_order():
    payload = {
        "customer": {
            "customer_name": "صيدلية العين",
            "customer_type": "pharmacy",
            "governorate": None,
            "area": None,
            "phone_number": None,
        },
        "transit": {
            "is_transit": False,
            "primary_customer": None,
            "destination_customer": None,
            "destination_type": "unknown",
        },
        "products": [
            {
                "written_product_name": "فانكو",
                "quantity": 50,
                "free_quantity": 0,
                "free_percentage": None,
                "expiry_date": None,
                "notes": None,
            }
        ],
        "order_notes": [],
        "mentioned_people": [],
        "missing_information": ["governorate"],
        "confidence_score": 0.95,
    }

    response = client.post("/api/orders/apply-rules", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["price_type"] == "pharmacy"
    assert body["price_type_requires_confirmation"] is False
    assert body["order_title"] == "صيدلية العين"
    assert body["can_generate_excel"] is False
    assert body["products_require_matching"] is True
    assert body["missing_information"] == []
    assert body["blocking_errors"] == []
    optional_fields = {
        item["details"]["field"] for item in body["informational_notices"]
    }
    assert optional_fields == {"governorate", "area", "phone_number"}
    assert body["can_proceed_to_product_matching"] is True
