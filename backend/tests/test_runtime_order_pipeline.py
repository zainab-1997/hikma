"""End-to-end API regressions for parse -> rules -> pharmaceutical matching."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from excel.catalog_reader import get_catalog_products
from main import app
from models.order_models import CustomerData, ParsedOrderResponse, ProductData, TransitData

client = TestClient(app)


def _mock_ai_response(customer_name: str, written_name: str, mistaken_quantity: int):
    parsed = ParsedOrderResponse(
        customer=CustomerData(customer_name=customer_name, customer_type="unknown"),
        transit=TransitData(),
        products=[
            ProductData(
                written_product_name=written_name,
                quantity=mistaken_quantity,
            )
        ],
        confidence_score=0.9,
    )
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(refusal=None, parsed=parsed))]
    )
    sdk = Mock()
    sdk.chat.completions.parse.return_value = completion
    return sdk


def _run_pipeline(message, customer_name, written_name, mistaken_quantity):
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="test-key",
        openai_model="test-model",
    )
    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch(
            "services.ai_parser_service.OpenAI",
            return_value=_mock_ai_response(customer_name, written_name, mistaken_quantity),
        ),
    ):
        parsed_response = client.post("/api/orders/parse", json={"message": message})
    assert parsed_response.status_code == 200
    parsed = parsed_response.json()

    rules_response = client.post(
        "/api/orders/apply-rules",
        json={**parsed, "price_type_override": None},
    )
    assert rules_response.status_code == 200
    reviewed = rules_response.json()

    match_response = client.post("/api/orders/match-products", json=reviewed)
    assert match_response.status_code == 200
    return parsed, reviewed, match_response.json()


@pytest.mark.parametrize(
    (
        "message",
        "customer_name",
        "written_name",
        "mistaken_quantity",
        "expected_customer_type",
        "expected_price_type",
        "expected_strength",
        "expected_quantity",
        "expected_row",
    ),
    [
        (
            "صيدلية العين\nفانكو ٥٠٠",
            "صيدلية العين",
            "فانكو",
            500,
            "pharmacy",
            "pharmacy",
            "500 mg",
            None,
            14,
        ),
        (
            "صيدلية الاختبار\nفانكو ٥٠٠ عدد ٢٠",
            "صيدلية العين",
            "فانكو",
            500,
            "pharmacy",
            "pharmacy",
            "500 mg",
            20,
            14,
        ),
        (
            "Test Pharmacy\nVanco 0.5 x 20",
            "Test Pharmacy",
            "Vanco",
            20,
            "pharmacy",
            "pharmacy",
            "500 mg",
            20,
            14,
        ),
        (
            "Test Pharmacy\nVanco 0.5",
            "Test Pharmacy",
            "Vanco",
            20,
            "pharmacy",
            "pharmacy",
            "500 mg",
            None,
            14,
        ),
        (
            "مذخر النور\nفانكو ١ غرام × 10",
            "مذخر النور",
            "فانكو",
            1,
            "drug_store",
            "drug_store",
            "1000 mg",
            10,
            13,
        ),
        (
            "Al Ain Pharmacy\nVanco 500 qty 20",
            "Al Ain Pharmacy",
            "Vanco",
            500,
            "pharmacy",
            "pharmacy",
            "500 mg",
            20,
            14,
        ),
        (
            "Al Noor Drug Store\nVanco 1g x 10",
            "Al Noor Drug Store",
            "Vanco",
            1,
            "drug_store",
            "drug_store",
            "1000 mg",
            10,
            13,
        ),
    ],
)
def test_actual_api_pipeline_separates_strength_quantity_and_price_type(
    message,
    customer_name,
    written_name,
    mistaken_quantity,
    expected_customer_type,
    expected_price_type,
    expected_strength,
    expected_quantity,
    expected_row,
):
    parsed, reviewed, matched = _run_pipeline(
        message, customer_name, written_name, mistaken_quantity
    )

    assert parsed["customer"]["customer_type"] == expected_customer_type
    assert parsed["products"][0]["strength"] == expected_strength
    assert parsed["products"][0]["quantity"] == expected_quantity

    assert reviewed["customer"]["customer_type"] == expected_customer_type
    assert reviewed["price_type"] == expected_price_type
    assert reviewed["price_type_requires_confirmation"] is False
    if expected_quantity is None:
        assert "quantity" in reviewed["missing_information"]
        assert any(
            item["type"] == "invalid_quantity"
            for item in reviewed["required_confirmations"]
        )

    product = matched["products"][0]
    assert product["strength"] == expected_strength
    assert product["quantity"] == expected_quantity
    assert product["match_status"] == "matched"
    assert product["matched_row"] == expected_row
    assert [candidate["row"] for candidate in product["candidates"]] == [expected_row]


@pytest.mark.parametrize(
    "product_line",
    [
        "Vanco 500 = 100",
        "Vanco 500mg = 100",
        "Vanco 500 mg - 100",
        "Vanco 500mg -100",
        "Vanco 500 / 100",
        "Vanco 500 x100",
        "Vanco 500 ×100",
        "Vanco 500 qty100",
        "Vanco 500 quantity100",
        "Vanco 500 عدد100",
        "Vanco 500 عدد 100",
        "Vanco 500 كمية100",
        "Vanco 500 كمية 100",
        "Vanco 500 100",
        "Vanco 0.5 = 100",
        "فانكو ٥٠٠ = ١٠٠",
        "فانكو ٥٠٠ ملغم = ١٠٠",
        "فانكو ٥٠٠-١٠٠",
        "فانكو ٥٠٠ / ١٠٠",
        "فانكو ٥٠٠ ×١٠٠",
        "فانكو ٥٠٠ عدد١٠٠",
        "فانكو ٥٠٠ كمية١٠٠",
    ],
)
def test_parse_endpoint_extracts_common_post_strength_quantity_styles(product_line):
    arabic = product_line.startswith("فانكو")
    customer_name = "صيدلية الاختبار" if arabic else "Test Pharmacy"
    written_name = "فانكو" if arabic else "Vanco"
    parsed, reviewed, matched = _run_pipeline(
        f"{customer_name}\n{product_line}",
        customer_name,
        written_name,
        None,
    )

    assert parsed["products"][0]["strength"] == "500 mg"
    assert parsed["products"][0]["quantity"] == 100
    assert parsed["products"][0]["free_quantity"] == 0
    assert reviewed["products"][0]["quantity"] == 100
    assert not any(error["type"] == "invalid_quantity" for error in reviewed["blocking_errors"])
    assert matched["products"][0]["quantity"] == 100
    assert matched["products"][0]["matched_row"] == 14


def test_quantity_and_free_quantity_are_extracted_independently():
    parsed, reviewed, matched = _run_pipeline(
        "Test Pharmacy\nVanco 500mg = 100 + 20",
        "Test Pharmacy",
        "Vanco",
        None,
    )

    for stage in (parsed, reviewed, matched):
        product = stage["products"][0]
        assert product["strength"] == "500 mg"
        assert product["quantity"] == 100
        assert product["free_quantity"] == 20


def test_right_side_pharmaceutical_attribute_is_not_treated_as_quantity():
    parsed, reviewed, matched = _run_pipeline(
        "Test Pharmacy\nVanco 500mg / 100ml",
        "Test Pharmacy",
        "Vanco",
        None,
    )
    assert parsed["products"][0]["quantity"] is None
    assert reviewed["products"][0]["quantity"] is None
    assert matched["products"][0]["quantity"] is None


def test_equals_quantity_style_applies_to_every_real_catalog_product():
    for catalog_product in get_catalog_products():
        product_line = f"{catalog_product.official_name} = 100"
        parsed, reviewed, matched = _run_pipeline(
            f"Test Pharmacy\n{product_line}",
            "Test Pharmacy",
            catalog_product.official_name,
            None,
        )
        assert parsed["products"][0]["quantity"] == 100
        assert reviewed["products"][0]["quantity"] == 100
        assert matched["products"][0]["quantity"] == 100
        assert matched["products"][0]["matched_row"] == catalog_product.row


@pytest.mark.parametrize(
    ("customer_name", "expected_type", "expected_price"),
    [
        ("Al Hayat Hospital", "hospital", "pharmacy"),
        ("مستشفى الحياة", "hospital", "pharmacy"),
        ("مخزن أدوية النور", "drug_store", "drug_store"),
        ("مكتب الحياة العلمي", "office", "drug_store"),
        ("Al Noor Warehouse", "drug_store", "drug_store"),
    ],
)
def test_customer_name_classification_is_generic_through_rules_endpoint(
    customer_name, expected_type, expected_price
):
    payload = ParsedOrderResponse(
        customer=CustomerData(customer_name=customer_name, customer_type="unknown"),
        transit=TransitData(),
        products=[ProductData(written_product_name="Vanco 500mg", quantity=1)],
        confidence_score=0.9,
    ).model_dump(mode="json")
    response = client.post(
        "/api/orders/apply-rules",
        json={**payload, "price_type_override": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["customer_type"] == expected_type
    assert body["price_type"] == expected_price
    assert body["price_type_requires_confirmation"] is False


def test_conflicting_customer_terms_require_manual_price_confirmation():
    payload = ParsedOrderResponse(
        customer=CustomerData(
            customer_name="Hospital Drug Store", customer_type="unknown"
        ),
        transit=TransitData(),
        products=[ProductData(written_product_name="Vanco 500mg", quantity=1)],
        confidence_score=0.9,
    ).model_dump(mode="json")
    response = client.post(
        "/api/orders/apply-rules",
        json={**payload, "price_type_override": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["customer_type"] == "unknown"
    assert body["price_type"] == "unknown"
    assert body["price_type_requires_confirmation"] is True
