"""Tests for the curated alias file (backend/data/product_aliases.json) against the real
Hikma catalog.

Unlike the general matching-algorithm tests, these intentionally read the real catalog
(read-only, via get_catalog_products() with no override) — an alias is only meaningful in
the context of the specific catalog it was curated for. Reading never writes to the
workbook; this mirrors the read-only checks already used elsewhere in the test suite.
"""

from excel.catalog_reader import get_catalog_products
from services.product_alias_service import load_alias_index
from services.product_matching_service import match_single_product
from utils.text_normalize import normalize_product_text


def _catalog():
    return get_catalog_products()


def test_atacure_alias_resolves_confidently():
    status, name, row, score, candidates = match_single_product("اتكيور", _catalog())
    assert status == "matched"
    assert row == 3
    assert "ATACURE" in name.upper()
    assert score == 1.0


def test_midazolam_alias_resolves_confidently():
    status, name, row, score, candidates = match_single_product("ميدازولام", _catalog())
    assert status == "matched"
    assert row == 6
    assert "MIDAZOLAM" in name.upper()
    assert score == 1.0


def test_vanco_500_alias_resolves_to_500mg_row():
    status, name, row, score, candidates = match_single_product("فانكو 500", _catalog())
    assert status == "matched"
    assert row == 14
    assert "500MG" in name.upper().replace(" ", "")


def test_vanco_500_with_arabic_digits_resolves_to_same_row():
    status, name, row, score, candidates = match_single_product("فانكو ٥٠٠", _catalog())
    assert status == "matched"
    assert row == 14


def test_vanco_1_gram_alias_resolves_to_1g_row():
    status, name, row, score, candidates = match_single_product("فانكو 1 غرام", _catalog())
    assert status == "matched"
    assert row == 13
    assert "1G" in name.upper().replace(" ", "")


def test_vanco_1_gram_no_space_variant_resolves_to_same_row():
    status, name, row, score, candidates = match_single_product("فانكو 1غرام", _catalog())
    assert status == "matched"
    assert row == 13


# --- ambiguity behavior: the whole point of NOT aliasing bare "فانكو" ---------------------


def test_plain_vanco_brand_is_ambiguous_not_guessed():
    status, name, row, score, candidates = match_single_product("فانكو", _catalog())
    assert status == "ambiguous"
    assert name is None
    assert row is None
    assert {candidate.row for candidate in candidates} == {13, 14}


def test_unregistered_arabic_word_does_not_falsely_trigger_an_alias():
    status, name, row, score, candidates = match_single_product("دواء غير معروف", _catalog())
    assert status == "unmatched"


# --- alias file loading itself --------------------------------------------------------


def test_alias_index_loads_expected_exact_entries():
    index = load_alias_index()
    assert index.exact.get("اتكيور") == 3
    assert index.exact.get("ميدازولام") == 6
    assert index.exact.get("فانكو 500") == 14
    assert index.exact.get(normalize_product_text("فانكو 1 غرام")) == 13


def test_alias_index_does_not_contain_a_bare_vanco_exact_alias():
    # Confirms the deliberate omission: a bare brand alias must never resolve to one row.
    index = load_alias_index()
    assert "فانكو" not in index.exact


def test_alias_index_loads_brand_alias():
    index = load_alias_index()
    assert index.brand.get("فانكو") == "vanco"
