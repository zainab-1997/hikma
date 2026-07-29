import pytest

from utils.route_format import (
    build_order_title,
    canonical_transit_title,
    detect_route_language,
    format_order_route,
)


@pytest.mark.parametrize(
    ("source", "destination", "expected"),
    [
        ("مذخر ساوا", "مستشفى الكوثر", "مذخر ساوا - ترانزيت - مستشفى الكوثر"),
        ("مذخر بغداد", "صيدلية الحياة", "مذخر بغداد - ترانزيت - صيدلية الحياة"),
        (
            "مكتب الحياة العلمي",
            "مستشفى اليرموك",
            "مكتب الحياة العلمي - ترانزيت - مستشفى اليرموك",
        ),
        (
            "مكتب بغداد العلمي",
            "صيدلية الشفاء",
            "مكتب بغداد العلمي - ترانزيت - صيدلية الشفاء",
        ),
    ],
)
def test_all_arabic_transit_routes_use_the_canonical_label(source, destination, expected):
    assert canonical_transit_title(source, destination) == expected


def test_english_ui_uses_english_transit_label():
    assert (
        format_order_route(
            "Baghdad Warehouse", "transit", "Al Shifa Pharmacy", "en"
        )
        == "Baghdad Warehouse - Transit - Al Shifa Pharmacy"
    )


def test_arabic_ui_uses_arabic_transit_label_even_with_latin_names():
    assert (
        format_order_route(
            "Baghdad Warehouse", "transit", "Al Shifa Pharmacy", "ar"
        )
        == "Baghdad Warehouse - ترانزيت - Al Shifa Pharmacy"
    )


def test_language_is_inferred_from_either_route_party():
    assert detect_route_language("Baghdad Warehouse", "صيدلية الشفاء") == "ar"
    assert detect_route_language("Baghdad Warehouse", "Al Shifa Pharmacy") == "en"


def test_standard_route_does_not_add_a_transit_label():
    assert format_order_route("صيدلية الشفاء", "standard", None, "ar") == "صيدلية الشفاء"


def test_central_title_builder_appends_only_present_location_parts():
    assert build_order_title(
        source_location="مذخر ساوة",
        is_transit=True,
        destination_customer="مستشفى الكوثر",
        governorate="البصرة",
        area="العشار",
    ) == "مذخر ساوة - ترانزيت - مستشفى الكوثر - البصرة - العشار"
