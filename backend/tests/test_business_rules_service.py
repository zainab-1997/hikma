"""Unit tests for the deterministic business-rules engine. No AI/OpenAI call is involved."""

from models.order_models import CustomerData, ProductData, TransitData
from models.review_order_models import ApplyRulesRequest
from services.business_rules_service import apply_business_rules


def _customer(**overrides):
    defaults = dict(customer_name="صيدلية العين", customer_type="pharmacy", governorate="النجف")
    defaults.update(overrides)
    return CustomerData(**defaults)


def _transit(**overrides):
    defaults = dict(is_transit=False)
    defaults.update(overrides)
    return TransitData(**defaults)


def _product(**overrides):
    defaults = dict(written_product_name="فانكو", quantity=50)
    defaults.update(overrides)
    return ProductData(**defaults)


def _request(**overrides) -> ApplyRulesRequest:
    defaults = dict(
        customer=_customer(),
        transit=_transit(),
        products=[_product()],
        order_notes=[],
        mentioned_people=[],
        missing_information=[],
        confidence_score=0.9,
        price_type_override=None,
    )
    defaults.update(overrides)
    return ApplyRulesRequest(**defaults)


# 1. Pharmacy uses Pharmacy Price.
def test_pharmacy_uses_pharmacy_price():
    result = apply_business_rules(_request(customer=_customer(customer_type="pharmacy")))
    assert result.price_type == "pharmacy"
    assert result.price_type_requires_confirmation is False


# 2. Hospital uses Pharmacy Price.
def test_hospital_uses_pharmacy_price():
    result = apply_business_rules(
        _request(customer=_customer(customer_name="مستشفى النجف", customer_type="hospital"))
    )
    assert result.price_type == "pharmacy"
    assert result.price_type_requires_confirmation is False


# 3. Drug Store uses Drug Store Price.
def test_drug_store_uses_drug_store_price():
    result = apply_business_rules(
        _request(customer=_customer(customer_name="مذخر الوافي", customer_type="drug_store"))
    )
    assert result.price_type == "drug_store"
    assert result.price_type_requires_confirmation is False


# 4. Office requires price confirmation.
def test_scientific_office_uses_drug_store_price():
    result = apply_business_rules(
        _request(customer=_customer(customer_name="مكتب بغداد", customer_type="office"))
    )
    assert result.price_type == "drug_store"
    assert result.price_type_requires_confirmation is False
    assert not any(c.type == "office_price_type" for c in result.required_confirmations)


def test_office_price_override_resolves_confirmation():
    result = apply_business_rules(
        _request(
            customer=_customer(customer_name="مكتب بغداد", customer_type="office"),
            price_type_override="drug_store",
        )
    )
    assert result.price_type == "drug_store"
    assert result.price_type_requires_confirmation is False
    assert not any(c.type == "office_price_type" for c in result.required_confirmations)


# 5. Non-transit title with governorate.
def test_non_transit_title_with_governorate():
    result = apply_business_rules(
        _request(customer=_customer(customer_name="صيدلية العين", governorate="النجف"))
    )
    assert result.order_title == "صيدلية العين - النجف"


# 6. Non-transit title without governorate.
def test_non_transit_title_without_governorate():
    result = apply_business_rules(
        _request(customer=_customer(customer_name="صيدلية العين", governorate=None))
    )
    assert result.order_title == "صيدلية العين"
    assert "governorate" not in result.missing_information
    assert any(
        notice.details["field"] == "governorate"
        for notice in result.informational_notices
    )
    assert result.can_proceed_to_product_matching is True


# 7. Transit title formatting.
def test_transit_title_formatting():
    result = apply_business_rules(
        _request(
            transit=_transit(
                is_transit=True,
                primary_customer="مذخر الوافي",
                destination_customer="صيدلية العين",
            ),
            customer=_customer(customer_name=None, customer_type="unknown", governorate="النجف"),
        )
    )
    assert result.order_title == "مذخر الوافي - ترانزيت - صيدلية العين - النجف"


# 8. Transit pricing based on primary customer.
def test_transit_pricing_uses_primary_customer():
    result = apply_business_rules(
        _request(
            transit=_transit(
                is_transit=True,
                primary_customer="مذخر الوافي",
                destination_customer="صيدلية العين",
            ),
            customer=_customer(customer_name=None, customer_type="unknown", governorate="النجف"),
        )
    )
    assert result.price_type == "drug_store"
    assert result.transit.primary_customer == "مذخر الوافي"
    assert result.transit.destination_customer == "صيدلية العين"


def test_office_transit_uses_drug_store_price():
    result = apply_business_rules(
        _request(
            transit=_transit(
                is_transit=True,
                primary_customer="مكتب بغداد",
                destination_customer="مستشفى النجف",
            ),
            customer=_customer(customer_name=None, customer_type="unknown", governorate="النجف"),
        )
    )
    assert result.price_type == "drug_store"
    assert result.price_type_requires_confirmation is False
    assert not any(c.type == "office_price_type" for c in result.required_confirmations)
    assert result.transit.primary_customer == "مكتب بغداد"
    assert result.transit.destination_customer == "مستشفى النجف"


# 9. Percentage bonus conversion.
def test_percentage_bonus_conversion():
    result = apply_business_rules(_request(products=[_product(quantity=100, free_percentage=20)]))
    assert result.products[0].free_quantity == 20
    assert result.products[0].free_percentage == 20


# 10. Percentage greater than 100.
def test_percentage_greater_than_100():
    result = apply_business_rules(_request(products=[_product(quantity=1000, free_percentage=130)]))
    assert result.products[0].free_quantity == 1300


# 11. Non-integer percentage result requires confirmation.
def test_non_integer_percentage_requires_confirmation():
    result = apply_business_rules(_request(products=[_product(quantity=7, free_percentage=15)]))
    assert any(w.type == "non_integer_free_quantity" for w in result.blocking_errors)
    assert any(c.type == "non_integer_free_quantity" for c in result.required_confirmations)
    assert result.can_proceed_to_product_matching is False


# 12. Ambiguous transit parties are not guessed.
def test_ambiguous_transit_parties_not_guessed():
    result = apply_business_rules(
        _request(
            transit=_transit(
                is_transit=True,
                primary_customer="فرع بغداد",
                destination_customer="فرع البصرة",
            ),
            customer=_customer(customer_name=None, customer_type="unknown", governorate=None),
        )
    )
    assert any(c.type == "ambiguous_transit_parties" for c in result.required_confirmations)
    assert result.transit.primary_customer == "فرع بغداد"
    assert result.transit.destination_customer == "فرع البصرة"
    assert result.can_generate_excel is False


# 13. Invalid quantity is blocked.
def test_invalid_quantity_is_blocked():
    result = apply_business_rules(_request(products=[_product(quantity=0)]))
    assert any(w.type == "invalid_quantity" for w in result.blocking_errors)
    assert any(c.type == "invalid_quantity" for c in result.required_confirmations)
    assert result.can_proceed_to_product_matching is False


# 14. Duplicate written product is flagged.
def test_duplicate_product_is_flagged():
    result = apply_business_rules(
        _request(
            products=[
                _product(written_product_name="فانكو", quantity=50),
                _product(written_product_name="فانكو", quantity=20),
            ]
        )
    )
    assert any(w.type == "duplicate_product" for w in result.blocking_errors)
    assert len(result.products) == 2
    assert result.can_proceed_to_product_matching is False


# 15. Optional fields do not block processing.
def test_optional_fields_do_not_block_processing():
    result = apply_business_rules(
        _request(
            customer=_customer(phone_number=None, area=None),
            products=[_product(expiry_date=None, notes=None)],
        )
    )
    assert result.can_proceed_to_product_matching is True
    assert "phone_number" not in result.missing_information
    assert "area" not in result.missing_information


def test_missing_governorate_area_and_phone_are_informational_only():
    result = apply_business_rules(
        _request(
            customer=_customer(governorate=None, area=None, phone_number=None),
            missing_information=[
                "governorate is missing",
                "governorate",
                "area",
                "phone number not provided",
            ],
        )
    )

    assert result.blocking_errors == []
    assert result.required_confirmations == []
    assert result.missing_information == []
    assert result.can_proceed_to_product_matching is True
    fields = [notice.details["field"] for notice in result.informational_notices]
    assert fields == ["governorate", "area", "phone_number"]
    assert all(
        notice.message.startswith("Optional information not provided:")
        for notice in result.informational_notices
    )


def test_transit_missing_destination_remains_blocked():
    result = apply_business_rules(
        _request(
            transit=_transit(
                is_transit=True,
                primary_customer="مذخر الوافي",
                destination_customer=None,
            ),
            customer=_customer(customer_name=None, customer_type="unknown"),
        )
    )

    assert "destination_customer" in result.missing_information
    assert any(
        error.details["field"] == "destination_customer"
        for error in result.blocking_errors
    )
    assert result.can_proceed_to_product_matching is False


def test_unknown_customer_type_requires_confirmation_but_optional_fields_do_not():
    result = apply_business_rules(
        _request(
            customer=_customer(
                customer_name="عميل تجريبي",
                customer_type="unknown",
                governorate=None,
                area=None,
                phone_number=None,
            )
        )
    )

    assert any(
        confirmation.type == "customer_type_or_price_type"
        for confirmation in result.required_confirmations
    )
    assert result.price_type == "unknown"
    assert result.can_proceed_to_product_matching is False
