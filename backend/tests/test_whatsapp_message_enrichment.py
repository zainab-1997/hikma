"""Regression coverage for deterministic WhatsApp quantity/location enrichment."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.order_models import CustomerData, ParsedOrderResponse, ProductData, TransitData
from services.order_text_postprocessor import (
    _quantity_and_product_text,
    postprocess_parsed_order,
)
from utils.location_normalize import extract_iraqi_customer_location


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("فانكو 500 100", 100),
        ("فانكو 500 ×100", 100),
        ("فانكو 500 x100", 100),
        ("فانكو 500 *100", 100),
        ("فانكو 500 (100)", 100),
        ("فانكو 500 - 100", 100),
        ("فانكو 500 عدد 100", 100),
        ("فانكو 500 كمية 100", 100),
        ("فانكو 500 =100", 100),
        ("فانكو 500 :100", 100),
        ("Vanco 500 100", 100),
        ("Vanco 500 Qty 100", 100),
        ("Vanco 500 Qty:100", 100),
        ("Vanco 500 Quantity 100", 100),
        ("Vanco 500 pcs 100", 100),
        ("Vanco 500 100 pcs", 100),
        ("Vanco 500 100 amp", 100),
        ("Vanco 500 100 vial", 100),
        ("فانكو ٥٠٠ = ١٠٠", 100),
        ("Product 500 × ٥٠", 50),
        ("Product 500 عدد ٢٥", 25),
    ],
)
def test_common_quantity_styles_keep_strength_separate(line, expected):
    quantity, product_text = _quantity_and_product_text(line)

    assert quantity == expected
    assert "500" in product_text or "٥٠٠" in product_text
    assert str(expected) not in product_text.replace("500", "").replace("٥٠٠", "")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("صيدلية الشفاء\nبغداد\nالمنصور", ("بغداد", None, "المنصور")),
        ("المحافظة: بغداد\nالمنصور", ("بغداد", None, "المنصور")),
        ("مدينة بغداد\nحي الجامعة", ("بغداد", "بغداد", "حي الجامعة")),
        ("صيدلية الشفاء\nبغداد / المنصور", ("بغداد", None, "المنصور")),
        ("مستشفى الكوثر\nالنجف - حي الأمير", ("النجف", None, "حي الأمير")),
        ("صيدلية\nالموصل الجامعة", ("نينوى", "الموصل", "الجامعة")),
        ("مذخر\nالبصرة الجمهورية", ("البصرة", None, "الجمهورية")),
    ],
)
def test_customer_location_is_extracted_without_area_name_registry(message, expected):
    assert extract_iraqi_customer_location(message) == expected


def test_location_labels_on_one_line_are_extracted_and_preserve_original_spelling():
    message = "المحافظة: بغداد، المدينة: بغداد، المنطقة: حي الجامعة"

    assert extract_iraqi_customer_location(message) == ("بغداد", "بغداد", "حي الجامعة")
    assert message == "المحافظة: بغداد، المدينة: بغداد، المنطقة: حي الجامعة"


def test_explicit_area_is_kept_even_when_governorate_is_not_present():
    assert extract_iraqi_customer_location("المنطقة: المنصور") == (
        None,
        None,
        "المنصور",
    )


def _ai_shape(product_names, *, transit=False):
    return ParsedOrderResponse(
        customer=CustomerData(customer_name=None, customer_type="unknown"),
        transit=TransitData(
            is_transit=transit,
            primary_customer="مذخر المصدر" if transit else None,
            destination_customer="صيدلية الوجهة" if transit else None,
        ),
        products=[ProductData(written_product_name=name) for name in product_names],
        missing_information=["governorate is missing", "quantity is missing"],
        confidence_score=0.9,
    )


def test_multiple_mixed_language_products_and_header_are_enriched():
    message = "صيدلية الشفاء\nبغداد / المنصور\nVanco 500 Qty:100\nمنتج ٢٥٠ × ٥٠"
    with patch("services.order_text_postprocessor.get_catalog_products", return_value=()):
        parsed = postprocess_parsed_order(message, _ai_shape(["Vanco", "منتج"]))

    assert parsed.customer.customer_name == "صيدلية الشفاء"
    assert parsed.customer.customer_type == "pharmacy"
    assert parsed.customer.governorate == "بغداد"
    assert parsed.customer.area == "المنصور"
    assert [product.quantity for product in parsed.products] == [100, 50]
    assert parsed.missing_information == []


def test_single_line_order_extracts_unlabelled_area_before_product_generically():
    message = "صيدلية العين بغداد الكراده ميدازولام = 10"
    ai_result = _ai_shape(["ميدازولام"])
    ai_result.customer.customer_name = "صيدلية العين"

    with patch("services.order_text_postprocessor.get_catalog_products", return_value=()):
        parsed = postprocess_parsed_order(message, ai_result)

    assert parsed.customer.governorate == "بغداد"
    assert parsed.customer.area == "الكراده"
    assert parsed.products[0].quantity == 10
    assert parsed.products[0].written_product_name == "ميدازولام"


def test_transit_destination_receives_explicit_location():
    message = "مذخر المصدر ترانزيت صيدلية الوجهة\nالنجف - حي الأمير\nProduct 500 = ١٠٠"
    with patch("services.order_text_postprocessor.get_catalog_products", return_value=()):
        parsed = postprocess_parsed_order(message, _ai_shape(["Product"], transit=True))

    assert parsed.products[0].quantity == 100
    assert parsed.transit.destination_governorate == "النجف"
    assert parsed.transit.destination_area == "حي الأمير"


def test_real_parse_route_returns_deterministically_enriched_fields():
    message = "صيدلية الشفاء\nبغداد\nالمنصور\nVanco 500 mg = ١٠٠"

    def parse_like_runtime(raw_message):
        with patch("services.order_text_postprocessor.get_catalog_products", return_value=()):
            return postprocess_parsed_order(raw_message, _ai_shape(["Vanco 500 mg"]))

    with patch("api.orders.parse_whatsapp_order", side_effect=parse_like_runtime):
        response = TestClient(app).post("/api/orders/parse", json={"message": message})

    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["customer_name"] == "صيدلية الشفاء"
    assert body["customer"]["governorate"] == "بغداد"
    assert body["customer"]["area"] == "المنصور"
    assert body["products"][0]["quantity"] == 100
