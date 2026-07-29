import pytest

from models.order_models import CustomerData, ParsedOrderResponse, ProductData, TransitData
from services.business_rules_service import apply_business_rules
from services.order_text_postprocessor import postprocess_parsed_order
from utils.location_normalize import extract_iraqi_location


@pytest.mark.parametrize(
    ("text", "governorate", "city"),
    [
        ("العنوان: البصرة", "البصرة", None),
        ("الموصل", "نينوى", "الموصل"),
        ("اربيل", "أربيل", None),
        ("Al Basra", "Basra", None),
        ("Mosul", "Nineveh", "Mosul"),
        ("Hawler", "Erbil", None),
        ("Salah Al-Din", "Salah Al-Din", None),
        ("Dhi Qar", "Dhi Qar", None),
    ],
)
def test_iraqi_location_variations_are_canonical(text, governorate, city):
    assert extract_iraqi_location(text) == (governorate, city)


def _parsed(*, transit=False):
    return ParsedOrderResponse(
        customer=CustomerData(
            customer_name=None if transit else "صيدلية الشفاء",
            customer_type="unknown",
        ),
        transit=TransitData(
            is_transit=transit,
            primary_customer="مذخر ساوة" if transit else None,
            destination_customer="مستشفى الكوثر" if transit else None,
        ),
        products=[ProductData(written_product_name="VANCO 500MG", quantity=10)],
        confidence_score=1,
    )


def test_location_survives_parse_postprocessing_and_business_rules_for_transit():
    parsed = postprocess_parsed_order(
        "مذخر ساوة ترانزيت مستشفى الكوثر\nالبصرة\nVANCO 500MG عدد 10",
        _parsed(transit=True),
    )
    review = apply_business_rules(parsed)

    assert parsed.customer.governorate == "البصرة"
    assert parsed.transit.destination_governorate == "البصرة"
    assert review.customer.governorate == "البصرة"
    assert review.transit.destination_governorate == "البصرة"
    assert review.order_title == "مذخر ساوة - ترانزيت - مستشفى الكوثر - البصرة"


def test_location_survives_parse_postprocessing_and_business_rules_for_standard_order():
    parsed = postprocess_parsed_order(
        "Al Shifa Pharmacy\nBaghdad\nVANCO 500MG qty 10",
        _parsed(),
    )
    parsed.customer.customer_name = "Al Shifa Pharmacy"
    review = apply_business_rules(parsed)

    assert review.customer.governorate == "Baghdad"
    assert review.order_title == "Al Shifa Pharmacy - Baghdad"
