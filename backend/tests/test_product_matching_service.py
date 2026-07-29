"""Unit tests for the deterministic product-matching engine. No AI/OpenAI call is involved.

All tests use a small, hand-built synthetic catalog — none of them depend on the real
backend/templates/Hikma orders.xlsx workbook.
"""

import pytest

from excel.catalog_reader import CatalogProduct, get_catalog_products
from models.order_models import CustomerData, ProductData, TransitData
from models.review_order_models import ReviewOrderResponse
from services.product_matching_service import (
    AUTO_MATCH_THRESHOLD,
    InvalidProductSelectionError,
    _has_strength_conflict,
    _normalize,
    _profile,
    match_order_products,
    match_products,
    match_single_product,
    search_catalog_products,
    validate_manual_selection,
)
from utils.text_normalize import normalize_product_text

CATALOG = (
    CatalogProduct(
        row=3,
        official_name="ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)",
        alias="ATRACURIUM BESILATE",
    ),
    CatalogProduct(
        row=4,
        official_name="VANCO 1G IV INFU VIALS (VANCOMYCIN 1G IV)",
        alias="VANCOMYCIN 1G IV",
    ),
    CatalogProduct(row=5, official_name="VANCO 500MG IV INFU VIALS 1'S"),
    CatalogProduct(row=6, official_name="SETRON 4MG/2ML IV AMP 5'S O"),
    CatalogProduct(row=7, official_name="SETRON 8MG/4ML IV AMP 5'S O"),
    CatalogProduct(row=8, official_name="TEKAM 50MG 10ML (KETAMINE)", alias="KETAMINE"),
)


# --- core matching statuses -------------------------------------------------------------


def test_exact_match():
    status, name, row, score, candidates = match_single_product(
        "TEKAM 50MG 10ML (KETAMINE)", CATALOG
    )
    assert status == "matched"
    assert row == 8
    assert score == 1.0


def test_alias_match():
    status, name, row, score, candidates = match_single_product("Atracurium Besilate", CATALOG)
    assert status == "matched"
    assert row == 3
    assert name == "ATACURE 50 MG / 5 ML (ATRACURIUM BESILATE)"


def test_arabic_digit_normalization():
    status, name, row, score, candidates = match_single_product(
        "TEKAM ٥٠MG 10ML (KETAMINE)", CATALOG
    )
    assert status == "matched"
    assert row == 8
    assert score == 1.0


def test_case_and_spacing_normalization():
    status, name, row, score, candidates = match_single_product(
        "  Tekam   50MG 10ml (Ketamine)  ", CATALOG
    )
    assert status == "matched"
    assert row == 8
    assert score == 1.0


def test_fuzzy_match_requires_confirmation():
    status, name, row, score, candidates = match_single_product("TEKAM 50MG SOLUTION", CATALOG)
    assert status == "fuzzy"
    assert name is None
    assert row is None
    # The name and strength are highly relevant, but the catalog does not state the
    # entered dosage form, so the safety gate still requires review.
    assert candidates[0].score >= 0.85
    assert candidates[0].row == 8


def test_ambiguous_match_returns_alternatives():
    status, name, row, score, candidates = match_single_product("VANCO", CATALOG)
    assert status == "ambiguous"
    assert name is None
    assert row is None
    assert {c.row for c in candidates} == {4, 5}


def test_unmatched_product_stays_unresolved():
    status, name, row, score, candidates = match_single_product("Amoxicillin Capsules", CATALOG)
    assert status == "unmatched"
    assert name is None
    assert row is None
    assert candidates == []


# --- strength-aware conflict handling ----------------------------------------------------


def test_strength_conflict_is_blocked():
    written = _normalize("VANCO 500MG")
    official = _normalize("VANCO 1G IV INFU VIALS (VANCOMYCIN 1G IV)")
    assert _has_strength_conflict(written, official) is True


def test_vanco_500_does_not_auto_match_vanco_1g():
    status, name, row, score, candidates = match_single_product("VANCO 500MG", CATALOG)
    assert status == "matched"
    assert row == 5
    assert all(candidate.row != 4 for candidate in candidates)


def test_1g_and_1000mg_are_treated_as_equivalent_where_safe():
    written = _normalize("VANCO 1000MG")
    official = _normalize("VANCO 1G IV INFU VIALS (VANCOMYCIN 1G IV)")
    assert _has_strength_conflict(written, official) is False

    # Pharmaceutical equivalence now supplies enough evidence to auto-match the unique
    # compatible strength; the true mismatch (500mg) is absent.
    status, name, row, score, candidates = match_single_product("VANCO 1000MG", CATALOG)
    assert status == "matched"
    assert row == 4
    assert candidates[0].row == 4


def test_strength_conflict_status_when_every_plausible_candidate_is_blocked():
    # A strength that matches neither catalog Vanco variant: both rows look textually
    # plausible (same brand) but disagree on dosage — this is a distinct, more actionable
    # status than a generic "unmatched", since the brand really was recognized.
    status, name, row, score, candidates = match_single_product("VANCO 250MG", CATALOG)
    assert status == "strength_conflict"
    assert name is None
    assert row is None
    assert {candidate.row for candidate in candidates} == {4, 5}


# --- pharmaceutical normalization and multi-attribute scoring ----------------------------


def test_arabic_letters_diacritics_numbers_and_units_are_normalized():
    assert normalize_product_text("أَلْفَا ١٬٠٠٠ مليغرام") == "الفا 1000 mg"
    assert normalize_product_text("٥٠ ملغم / ٥ مل") == "50 mg/5 ml"


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("٥٠٠ ملغ", "500 mg"),
        ("٥٠٠ ملغم", "500 mg"),
        ("٥٠٠ مليغرام", "500 mg"),
        ("٥٠٠ ملي غرام", "500 mg"),
        ("٥٠٠ مغ", "500 mg"),
        ("١ غ", "1 g"),
        ("١ غم", "1 g"),
        ("١ غرام", "1 g"),
        ("١ جرام", "1 g"),
        ("١٠٠٠ مكغ", "1000 mcg"),
        ("١٠٠٠ ميكروغرام", "1000 mcg"),
        ("١٠٠٠ ميكرو غرام", "1000 mcg"),
        ("500 ملغ", "500 mg"),
        ("۵۰۰ ملغ", "500 mg"),
    ],
)
def test_all_common_arabic_mass_unit_spellings_are_canonical(written, expected):
    assert normalize_product_text(written) == expected


@pytest.mark.parametrize(
    "written",
    [
        "MED 500mg",
        "MED 500 mg",
        "MED 500-mg",
        "MED 500 / mg",
        "MED 0.5 g",
        "MED ٠.٥ غرام",
        "MED نص غرام",
        "MED ١/٢ غرام",
    ],
)
def test_english_arabic_decimal_fractional_and_format_variants_share_strength(written):
    profile = _profile(written)
    assert profile.name_tokens == frozenset({"med"})
    assert profile.strengths == {"mass_mg": frozenset({500.0})}


@pytest.mark.parametrize("written", ["MICRO 1000 mcg", "MICRO 1000 μg", "MICRO ١٠٠٠ مكغ"])
def test_microgram_spellings_and_symbols_convert_to_canonical_milligrams(written):
    assert _profile(written).strengths == {"mass_mg": frozenset({1.0})}


@pytest.mark.parametrize(
    ("written", "canonical_form"),
    [
        ("Ampoule", "amp"),
        ("امبول", "amp"),
        ("Vial", "vial"),
        ("فيال", "vial"),
        ("Tab", "tablet"),
        ("قرص", "tablet"),
        ("Cap", "capsule"),
        ("كبسولة", "capsule"),
        ("Susp", "suspension"),
        ("معلق", "suspension"),
        ("Inj", "injection"),
        ("حقن", "injection"),
        ("IV", "iv"),
        ("وريدي", "iv"),
        ("IM", "im"),
        ("عضلي", "im"),
        ("PO", "po"),
        ("فموي", "po"),
    ],
)
def test_english_and_arabic_dosage_form_abbreviations_are_canonical(
    written, canonical_form
):
    assert canonical_form in _profile(written).forms


def test_arabic_fraction_and_gram_conversion_uniquely_select_strength():
    catalog = (
        CatalogProduct(row=3, official_name="GENERIC 500MG TABLET 10"),
        CatalogProduct(row=4, official_name="GENERIC 250MG TABLET 10"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "GENERIC نص غرام قرص", catalog
    )
    assert status == "matched"
    assert row == 3
    assert [candidate.row for candidate in candidates] == [3]


def test_mcg_to_mg_conversion_with_dosage_form_is_generic_and_safe():
    catalog = (
        CatalogProduct(row=3, official_name="MICRO 1MG INJECTION VIAL 1"),
        CatalogProduct(row=4, official_name="MICRO 500MCG INJECTION VIAL 1"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "MICRO 1000 μg inj vial 1", catalog
    )
    assert status == "matched"
    assert row == 3
    assert all(candidate.row != 4 for candidate in candidates)


def test_mixed_arabic_english_units_routes_forms_and_volume_auto_match():
    catalog = (
        CatalogProduct(
            row=3,
            official_name="INSULIN 100 IU/ML INJECTION VIAL 10ML",
        ),
    )
    status, _name, row, score, _candidates = match_single_product(
        "INSULIN ١٠٠ وحدة دولية/مل حقن فيال ١٠ مل", catalog
    )
    assert status == "matched"
    assert row == 3
    assert score == 1.0


def test_arabic_dosage_form_selects_tablet_not_capsule():
    catalog = (
        CatalogProduct(row=3, official_name="ORBIT 10MG TABLET 20"),
        CatalogProduct(row=4, official_name="ORBIT 10MG CAPSULE 20"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "ORBIT ١٠ ملغم قرص", catalog
    )
    assert status == "matched"
    assert row == 3
    assert all(candidate.row != 4 for candidate in candidates)


def test_equivalent_mass_per_volume_concentrations_select_unique_product():
    catalog = (
        CatalogProduct(row=3, official_name="BETA 5MG/ML IV AMP 5"),
        CatalogProduct(row=4, official_name="BETA 10MG/ML IV AMP 5"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "BETA ٠.٥ غرام/١٠٠ مل وريدي امبول 5", catalog
    )
    assert status == "matched"
    assert row == 3
    assert all(candidate.row != 4 for candidate in candidates)


def test_percentage_concentration_is_normalized_and_safely_disambiguated():
    catalog = (
        CatalogProduct(row=3, official_name="DERMA 1% SOLUTION"),
        CatalogProduct(row=4, official_name="DERMA 2% SOLUTION"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "DERMA ١% محلول", catalog
    )
    assert status == "matched"
    assert row == 3
    assert all(candidate.row != 4 for candidate in candidates)


def test_arabic_package_size_selects_unique_catalog_product():
    catalog = (
        CatalogProduct(row=3, official_name="GAMMA 10MG TABLET 10"),
        CatalogProduct(row=4, official_name="GAMMA 10MG TABLET 20"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "GAMMA 10mg ٢٠ قرص", catalog
    )
    assert status == "matched"
    assert row == 4
    assert all(candidate.row != 3 for candidate in candidates)


def test_conflicting_package_size_is_a_safety_veto():
    catalog = (CatalogProduct(row=3, official_name="GAMMA 10MG TABLET 10"),)
    status, name, row, score, candidates = match_single_product(
        "GAMMA 10MG TABLET 20", catalog
    )
    assert status == "strength_conflict"
    assert name is None
    assert row is None
    assert score is None
    assert candidates[0].row == 3


def test_omitted_package_size_remains_ambiguous_when_multiple_packages_exist():
    catalog = (
        CatalogProduct(row=3, official_name="GAMMA 10MG TABLET 10"),
        CatalogProduct(row=4, official_name="GAMMA 10MG TABLET 20"),
    )
    status, _name, row, _score, candidates = match_single_product(
        "GAMMA 10MG TABLET", catalog
    )
    assert status == "ambiguous"
    assert row is None
    assert {candidate.row for candidate in candidates} == {3, 4}


def test_transliteration_and_safe_spelling_variant_auto_matches_with_attributes():
    catalog = (CatalogProduct(row=3, official_name="ALPHA 1000MG/10ML IV VIAL 1"),)
    status, name, row, score, candidates = match_single_product(
        "Alfa 1000 ملغم / 10 مل وريدي فيال", catalog
    )
    assert status == "matched"
    assert row == 3
    assert score >= AUTO_MATCH_THRESHOLD


def test_manufacturer_name_is_not_required_for_a_clear_match():
    catalog = (
        CatalogProduct(row=3, official_name="Levofloxacin Hikma 500MG/100ML IV VIAL 1"),
    )
    status, name, row, score, candidates = match_single_product(
        "Levofloxacin 500mg/100ml IV vial", catalog
    )
    assert status == "matched"
    assert row == 3


def test_dosage_form_conflict_never_auto_matches():
    catalog = (
        CatalogProduct(row=3, official_name="ALPHA 1000MG TABLET 10"),
        CatalogProduct(row=4, official_name="ALPHA 1000MG IV VIAL 1"),
    )
    status, name, row, score, candidates = match_single_product(
        "Alpha 1000mg capsule", catalog
    )
    assert status == "strength_conflict"
    assert row is None
    assert {candidate.row for candidate in candidates} == {3, 4}


def test_concentration_conflict_is_blocked_and_compatible_ratio_is_selected():
    catalog = (
        CatalogProduct(row=3, official_name="BETA 10MG/2ML IV AMP 5"),
        CatalogProduct(row=4, official_name="BETA 10MG/5ML IV AMP 5"),
    )
    status, name, row, score, candidates = match_single_product(
        "Beta 5mg/ml IV amp", catalog
    )
    assert status == "matched"
    assert row == 3
    assert all(candidate.row != 4 for candidate in candidates)


def test_missing_strength_stays_ambiguous_when_catalog_has_multiple_strengths():
    status, name, row, score, candidates = match_single_product("SETRON IV AMP", CATALOG)
    assert status == "ambiguous"
    assert row is None
    assert {candidate.row for candidate in candidates} == {6, 7}


def test_package_size_breaks_an_otherwise_equal_tie():
    catalog = (
        CatalogProduct(row=3, official_name="GAMMA 10MG TABLET 10"),
        CatalogProduct(row=4, official_name="GAMMA 10MG TABLET 20"),
    )
    status, name, row, score, candidates = match_single_product(
        "Gamma 10mg tablet 20", catalog
    )
    assert status == "matched"
    assert row == 4


def test_generic_name_and_partial_search_are_ranked_by_relevance():
    catalog = (
        CatalogProduct(
            row=3,
            official_name="ATACURE 50MG/5ML IV AMP (ATRACURIUM BESILATE)",
            alias="ATRACURIUM BESILATE",
        ),
        CatalogProduct(row=4, official_name="ATROPINE 1MG/ML IV AMP"),
    )
    results = search_catalog_products("atracurium", catalog)
    assert results[0].row == 3


def test_arabic_alias_search_finds_the_curated_catalog_row():
    results = search_catalog_products("اتكيور", get_catalog_products())
    assert results[0].row == 3


# --- duplicate catalog rows --------------------------------------------------------------


def test_duplicate_catalog_entries_surface_as_ambiguous_when_matched():
    catalog = (
        CatalogProduct(row=3, official_name="Alpha Tablet 50MG"),
        CatalogProduct(row=9, official_name="Alpha Tablet 50MG"),
    )
    status, name, row, score, candidates = match_single_product("Alpha Tablet 50MG", catalog)
    assert status == "ambiguous"
    assert len(candidates) == 2


# --- manual selection validation ---------------------------------------------------------


def test_manual_selection_is_validated_successfully():
    candidate = validate_manual_selection(8, "TEKAM 50MG 10ML (KETAMINE)", catalog=CATALOG)
    assert candidate.row == 8
    assert candidate.score == 1.0


def test_manual_selection_rejects_mismatched_official_name():
    with pytest.raises(InvalidProductSelectionError):
        validate_manual_selection(8, "Some Other Product Entirely", catalog=CATALOG)


def test_manual_selection_rejects_nonexistent_row():
    with pytest.raises(InvalidProductSelectionError):
        validate_manual_selection(999, "Anything", catalog=CATALOG)


# --- order-level matching -----------------------------------------------------------------


def _review_order(products: list[ProductData]) -> ReviewOrderResponse:
    return ReviewOrderResponse(
        customer=CustomerData(customer_name="صيدلية العين", customer_type="pharmacy", governorate="النجف"),
        transit=TransitData(),
        order_title="صيدلية العين - النجف",
        price_type="pharmacy",
        price_type_requires_confirmation=False,
        products=products,
        order_notes=[],
        warnings=[],
        required_confirmations=[],
        missing_information=[],
        confidence_score=0.9,
        can_generate_excel=False,
        can_proceed_to_product_matching=True,
        products_require_matching=True,
    )


def test_match_products_preserves_quantities_and_bonuses():
    matched = match_products(
        [ProductData(written_product_name="TEKAM 50MG 10ML (KETAMINE)", quantity=5, free_quantity=1)],
        catalog=CATALOG,
    )
    assert matched[0].quantity == 5
    assert matched[0].free_quantity == 1
    assert matched[0].match_status == "matched"


def test_match_order_products_all_matched_true_when_every_product_confident():
    review_order = _review_order(
        [ProductData(written_product_name="TEKAM 50MG 10ML (KETAMINE)", quantity=5)]
    )
    result = match_order_products(review_order, catalog=CATALOG)

    assert result.all_products_matched is True
    assert result.products_require_matching is False
    assert result.can_generate_excel is False
    assert result.products[0].match_status == "matched"


def test_match_order_products_all_matched_false_when_any_unresolved():
    review_order = _review_order(
        [ProductData(written_product_name="Amoxicillin Capsules", quantity=5)]
    )
    result = match_order_products(review_order, catalog=CATALOG)

    assert result.all_products_matched is False
    assert result.products[0].match_status == "unmatched"
