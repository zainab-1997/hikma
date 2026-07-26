"""Deterministic, pharmaceutical-attribute-aware product matching.

The public API remains unchanged. Internally, candidates are ranked using name identity,
curated aliases, strength, concentration, dosage form, and package information. Explicit
pharmaceutical conflicts are safety vetoes and can never be auto-selected.
"""

import logging
import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from excel.catalog_reader import CatalogProduct, get_catalog_products
from models.matched_order_models import MatchedOrderResponse, MatchedProductData, ProductMatchCandidate
from models.order_models import ProductData
from models.review_order_models import ReviewOrderResponse
from services.product_alias_service import load_alias_index
from utils.text_normalize import normalize_product_text as _normalize

EXACT_SCORE = 1.0
AUTO_MATCH_THRESHOLD = 0.86
AMBIGUITY_MARGIN = 0.06
CANDIDATE_THRESHOLD = 0.42
NAME_FAMILY_THRESHOLD = 0.76
MAX_CANDIDATES = 5

logger = logging.getLogger(__name__)

_MEASUREMENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(mcg|mg|g|ml|iu)\b")
_CONCENTRATION_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mcg|mg|g|iu)\s*/\s*(?:(\d+(?:\.\d+)?)\s*)?(ml)\b"
)
_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_VOLUME_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*ml\b")
_PACKAGE_BEFORE_FORM_PATTERN = re.compile(r"\b(\d+)\s*(amp|vial|tablet|capsule)s?\b")
_PACKAGE_AFTER_FORM_PATTERN = re.compile(r"\b(amp|vial|tablet|capsule)s?\s*(\d+)\b")
_LOOSE_PACKAGE_PATTERN = re.compile(r"\b(\d+)\s*s\b")
_STANDALONE_NUMBER_PATTERN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")
_MASS_UNITS_TO_MG = {"mcg": 0.001, "mg": 1.0, "g": 1000.0}
_FORMS = {
    "amp", "vial", "tablet", "capsule", "suspension", "injection",
    "solution", "syrup", "inhal", "infusion", "iv", "im", "po",
}
_FORM_GROUPS = (
    frozenset({"iv", "im", "po"}),
    frozenset({"tablet", "capsule", "suspension", "injection", "solution", "syrup", "inhal", "infusion"}),
    frozenset({"amp", "vial"}),
)
_NON_NAME_TOKENS = _FORMS | {
    "mcg", "mg", "g", "ml", "iu", "hikma", "pharma", "pharmaceutical",
    "s", "o",
}

_ALIAS_INDEX = load_alias_index()


class InvalidProductSelectionError(Exception):
    """Raised when a manual selection does not match the live catalog."""


@dataclass(frozen=True)
class ProductProfile:
    normalized: str
    name_tokens: frozenset[str]
    strengths: dict[str, frozenset[float]]
    concentrations: frozenset[tuple[str, float]]
    forms: frozenset[str]
    package_sizes: frozenset[tuple[str, int]]
    volumes_ml: frozenset[float]


@dataclass(frozen=True)
class ScoredProduct:
    product: CatalogProduct
    score: float
    name_score: float
    conflict: bool
    form_unverifiable: bool


def _canonical_measurement(value: float, unit: str) -> tuple[str, float]:
    if unit in _MASS_UNITS_TO_MG:
        return "mass_mg", round(value * _MASS_UNITS_TO_MG[unit], 6)
    return unit, round(value, 6)


def _extract_strengths(normalized_text: str) -> dict[str, set[float]]:
    strengths: dict[str, set[float]] = {}
    for raw_value, unit in _MEASUREMENT_PATTERN.findall(normalized_text):
        if unit == "ml":
            continue
        category, value = _canonical_measurement(float(raw_value), unit)
        strengths.setdefault(category, set()).add(value)
    return strengths


def _extract_concentrations(normalized_text: str) -> set[tuple[str, float]]:
    concentrations: set[tuple[str, float]] = set()
    for numerator, unit, denominator, _volume_unit in _CONCENTRATION_PATTERN.findall(normalized_text):
        category, canonical = _canonical_measurement(float(numerator), unit)
        ratio = canonical / float(denominator or 1)
        concentrations.add((f"{category}_per_ml", round(ratio, 6)))
    for percentage in _PERCENT_PATTERN.findall(normalized_text):
        concentrations.add(("percent", round(float(percentage), 6)))
    return concentrations


def _extract_forms(normalized_text: str) -> set[str]:
    forms = set(normalized_text.split()) & _FORMS
    # Ampoules/vials with a parenteral route are unambiguously injectable even when
    # the catalog omits the literal word "injection".
    if forms & {"amp", "vial"} and forms & {"iv", "im"}:
        forms.add("injection")
    return forms


def _extract_volumes(normalized_text: str) -> set[float]:
    denominator_spans = {
        match.span(4)
        for match in _CONCENTRATION_PATTERN.finditer(normalized_text)
    }
    volumes: set[float] = set()
    for match in _VOLUME_PATTERN.finditer(normalized_text):
        unit_start = match.span(0)[1] - 2
        if any(start <= unit_start < end for start, end in denominator_spans):
            continue
        volumes.add(round(float(match.group(1)), 6))
    return volumes


def _extract_package_sizes(normalized_text: str) -> set[tuple[str, int]]:
    packages: set[tuple[str, int]] = set()
    for count, form in _PACKAGE_BEFORE_FORM_PATTERN.findall(normalized_text):
        packages.add((form, int(count)))
    for form, count in _PACKAGE_AFTER_FORM_PATTERN.findall(normalized_text):
        packages.add((form, int(count)))
    for count in _LOOSE_PACKAGE_PATTERN.findall(normalized_text):
        packages.add(("unit", int(count)))
    return packages


def _name_tokens(normalized_text: str) -> frozenset[str]:
    tokens = []
    for token in re.findall(r"[\w]+", normalized_text):
        if token in _NON_NAME_TOKENS or token.isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", token):
            continue
        tokens.append(token)
    return frozenset(tokens)


def _profile(text: str) -> ProductProfile:
    normalized = _normalize(text)
    return ProductProfile(
        normalized=normalized,
        name_tokens=_name_tokens(normalized),
        strengths={key: frozenset(values) for key, values in _extract_strengths(normalized).items()},
        concentrations=frozenset(_extract_concentrations(normalized)),
        forms=frozenset(_extract_forms(normalized)),
        package_sizes=frozenset(_extract_package_sizes(normalized)),
        volumes_ml=frozenset(_extract_volumes(normalized)),
    )


def _extract_standalone_numbers(normalized_text: str) -> list[float]:
    """Return numeric tokens not already owned by a pharmaceutical attribute."""
    occupied: list[tuple[int, int]] = []
    for pattern in (
        _MEASUREMENT_PATTERN,
        _CONCENTRATION_PATTERN,
        _PERCENT_PATTERN,
        _PACKAGE_BEFORE_FORM_PATTERN,
        _PACKAGE_AFTER_FORM_PATTERN,
        _LOOSE_PACKAGE_PATTERN,
    ):
        occupied.extend(match.span() for match in pattern.finditer(normalized_text))

    return [
        float(match.group(1))
        for match in _STANDALONE_NUMBER_PATTERN.finditer(normalized_text)
        if not any(start <= match.start() and match.end() <= end for start, end in occupied)
    ]


def _infer_unitless_mass_strength(
    written: ProductProfile,
    family: list[tuple[CatalogProduct, float]],
) -> tuple[ProductProfile, str | None, float | None]:
    """Infer a bare number as grams only when the catalog family proves it is safe.

    We explicitly test other plausible mass interpretations against the same family.
    If more than one interpretation or catalog row remains possible, nothing is inferred.
    """
    if written.strengths or written.concentrations or not written.name_tokens:
        return written, None, None
    bare_numbers = _extract_standalone_numbers(written.normalized)
    if len(bare_numbers) != 1 or not family:
        return written, None, None

    family_profiles = [
        (product, _profile(product.official_name))
        for product, _name_score_value in family
    ]
    if any(not profile.strengths.get("mass_mg") for _product, profile in family_profiles):
        return written, None, None

    raw_value = bare_numbers[0]
    interpretations = {
        "g": round(raw_value * 1000.0, 6),
        "mg": round(raw_value, 6),
        "mcg": round(raw_value * 0.001, 6),
    }
    matching_rows_by_unit = {
        unit: {
            product.row
            for product, profile in family_profiles
            if canonical in profile.strengths.get("mass_mg", frozenset())
        }
        for unit, canonical in interpretations.items()
    }
    plausible = {
        unit: rows for unit, rows in matching_rows_by_unit.items() if rows
    }
    gram_rows = plausible.get("g", set())
    if len(plausible) != 1 or len(gram_rows) != 1:
        return written, None, None

    canonical = interpretations["g"]
    return (
        replace(written, strengths={"mass_mg": frozenset({canonical})}),
        "g",
        canonical,
    )


def _has_value_conflict(
    written: dict[str, frozenset[float]] | dict[str, set[float]],
    official: dict[str, frozenset[float]] | dict[str, set[float]],
) -> bool:
    for category, written_values in written.items():
        official_values = official.get(category)
        if official_values and set(written_values).isdisjoint(official_values):
            return True
    return False


def _has_strength_conflict(written_norm: str, official_norm: str) -> bool:
    return _has_value_conflict(_extract_strengths(written_norm), _extract_strengths(official_norm))


def _fuzzy_token_score(written: frozenset[str], official: frozenset[str]) -> float:
    if not written or not official:
        return 0.0
    def phonetic(token: str) -> str:
        return token.replace("ph", "f").replace("ck", "k").replace("qu", "k")

    per_token = [
        max(
            SequenceMatcher(None, phonetic(token), phonetic(candidate)).ratio()
            for candidate in official
        )
        for token in written
    ]
    return sum(per_token) / len(per_token)


def _name_score(written: ProductProfile, product: CatalogProduct) -> float:
    alternatives = [product.official_name]
    if product.alias:
        alternatives.append(product.alias)

    best = 0.0
    for alternative in alternatives:
        candidate = _profile(alternative)
        if written.normalized == candidate.normalized:
            return EXACT_SCORE
        if written.name_tokens and written.name_tokens <= candidate.name_tokens:
            best = max(best, 0.97)
            continue
        token_overlap = (
            len(written.name_tokens & candidate.name_tokens)
            / max(len(written.name_tokens), 1)
        )
        fuzzy = _fuzzy_token_score(written.name_tokens, candidate.name_tokens)
        sequence = SequenceMatcher(
            None,
            " ".join(sorted(written.name_tokens)),
            " ".join(sorted(candidate.name_tokens)),
        ).ratio()
        composite = 0.55 * fuzzy + 0.30 * token_overlap + 0.15 * sequence
        if fuzzy >= 0.8:
            composite = max(composite, 0.82 + 0.15 * ((fuzzy - 0.8) / 0.2))
        best = max(best, composite)
    return min(best, 1.0)


def _attribute_score(
    query_values,
    catalog_values,
    *,
    missing_catalog_score: float = 0.25,
) -> tuple[float | None, bool]:
    if not query_values:
        return None, False
    if not catalog_values:
        return missing_catalog_score, False
    return (1.0, False) if not set(query_values).isdisjoint(catalog_values) else (0.0, True)


def _strength_attribute_score(
    query_values: dict[str, frozenset[float]],
    catalog_values: dict[str, frozenset[float]],
) -> tuple[float | None, bool]:
    if not query_values:
        return None, False
    comparable = set(query_values) & set(catalog_values)
    if not comparable:
        return 0.25, False
    if _has_value_conflict(query_values, catalog_values):
        return 0.0, True
    return 1.0, False


def _form_attribute_score(
    query_forms: frozenset[str], catalog_forms: frozenset[str]
) -> tuple[float | None, bool]:
    if not query_forms:
        return None, False
    if not catalog_forms:
        return 0.25, False
    compared = 0
    matched = 0
    for group in _FORM_GROUPS:
        query_group = query_forms & group
        if not query_group:
            continue
        catalog_group = catalog_forms & group
        if not catalog_group:
            continue
        compared += 1
        if query_group.isdisjoint(catalog_group):
            return 0.0, True
        matched += 1
    if not compared:
        return 0.25, False
    return matched / compared, False


def _apply_brand_aliases(normalized: str) -> str:
    result = normalized
    for written, replacement in sorted(_ALIAS_INDEX.brand.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", replacement, result)
    return result


def _score_product(
    written: ProductProfile,
    product: CatalogProduct,
    *,
    name_score: float | None = None,
    official: ProductProfile | None = None,
) -> ScoredProduct:
    official = official or _profile(product.official_name)
    name_score = _name_score(written, product) if name_score is None else name_score

    # When both sides express concentration, numerator mass is not an independent dose:
    # 5mg/1ml and 10mg/2ml are equivalent. Let the canonical per-ml comparison decide.
    if written.concentrations and official.concentrations:
        strength_score, strength_conflict = None, False
    else:
        strength_score, strength_conflict = _strength_attribute_score(
            written.strengths, official.strengths
        )
    concentration_score, concentration_conflict = _attribute_score(
        written.concentrations, official.concentrations
    )
    form_score, form_conflict = _form_attribute_score(written.forms, official.forms)
    package_score, _package_conflict = _attribute_score(
        written.package_sizes, official.package_sizes, missing_catalog_score=0.5
    )
    volume_score, volume_conflict = _attribute_score(
        written.volumes_ml, official.volumes_ml, missing_catalog_score=0.25
    )
    conflict = (
        strength_conflict
        or concentration_conflict
        or form_conflict
        or _package_conflict
        or volume_conflict
    )
    unverifiable = bool(
        (written.strengths and not official.strengths)
        or (written.concentrations and not official.concentrations)
        or (written.forms and not official.forms)
        or (written.package_sizes and not official.package_sizes)
        or (written.volumes_ml and not official.volumes_ml)
    )

    # Pharmaceutical compatibility is a hard filter. Conflicting candidates never
    # receive a composite similarity score.
    if conflict:
        return ScoredProduct(
            product=product,
            score=0.0,
            name_score=round(name_score, 4),
            conflict=True,
            form_unverifiable=unverifiable,
        )

    components = [(0.65, name_score)]
    for weight, component in (
        (0.15, strength_score),
        (0.08, concentration_score),
        (0.06, form_score),
        (0.06, package_score),
        (0.05, volume_score),
    ):
        if component is not None:
            components.append((weight, component))
    total_weight = sum(weight for weight, _value in components)
    score = sum(weight * value for weight, value in components) / total_weight

    return ScoredProduct(
        product=product,
        score=round(score, 4),
        name_score=round(name_score, 4),
        conflict=False,
        form_unverifiable=unverifiable,
    )


def _exact_alias_candidate(
    normalized: str, catalog: tuple[CatalogProduct, ...]
) -> ProductMatchCandidate | None:
    row = _ALIAS_INDEX.exact.get(normalized)
    if row is None:
        return None
    product = next((item for item in catalog if item.row == row), None)
    if product is None:
        return None
    return ProductMatchCandidate(official_name=product.official_name, row=product.row, score=EXACT_SCORE)


def _rank_scored_products(
    written_product_name: str, catalog: tuple[CatalogProduct, ...]
) -> tuple[ProductProfile, list[ScoredProduct], list[ScoredProduct]]:
    normalized = _normalize(written_product_name)
    effective = _apply_brand_aliases(normalized)
    written = _profile(effective)
    catalog_profiles = {
        product.row: _profile(product.official_name) for product in catalog
    }
    name_ranked = [
        (product, _name_score(written, product))
        for product in catalog
    ]
    name_family = [
        item for item in name_ranked if item[1] >= NAME_FAMILY_THRESHOLD
    ]
    explicitly_extracted_strength = written.strengths
    written, inferred_unit, canonical_strength = _infer_unitless_mass_strength(
        written, name_family
    )

    scored = [
        _score_product(
            written,
            product,
            name_score=name_score,
            official=catalog_profiles[product.row],
        )
        for product, name_score in name_ranked
    ]
    usable = sorted(
        (item for item in scored if not item.conflict and item.score >= CANDIDATE_THRESHOLD),
        key=lambda item: (-item.score, item.product.row),
    )
    conflicted = sorted(
        (
            item for item in scored
            if item.conflict and item.name_score >= NAME_FAMILY_THRESHOLD
        ),
        key=lambda item: (-item.name_score, item.product.row),
    )
    logger.debug(
        "Pharmaceutical match trace raw=%r name_tokens=%s extracted_strength=%s "
        "inferred_unit=%s canonical_strength_mg=%s catalog_strengths=%s "
        "removed_rows=%s final_rows=%s",
        written_product_name,
        sorted(written.name_tokens),
        explicitly_extracted_strength,
        inferred_unit,
        canonical_strength,
        {
            product.row: catalog_profiles[product.row].strengths
            for product, name_score in name_ranked
            if name_score >= NAME_FAMILY_THRESHOLD
        },
        [item.product.row for item in conflicted],
        [item.product.row for item in usable],
    )
    return written, usable, conflicted


def _candidate(item: ScoredProduct) -> ProductMatchCandidate:
    return ProductMatchCandidate(
        official_name=item.product.official_name,
        row=item.product.row,
        score=item.score,
    )


def _omitted_discriminator_is_ambiguous(
    written: ProductProfile, family: list[ScoredProduct]
) -> bool:
    if len(family) < 2:
        return False
    profiles = [_profile(item.product.official_name) for item in family]
    if not written.strengths and len({repr(profile.strengths) for profile in profiles}) > 1:
        return True
    if not written.concentrations and len({profile.concentrations for profile in profiles}) > 1:
        return True
    if not written.forms and len({profile.forms for profile in profiles}) > 1:
        return True
    if not written.package_sizes and len({profile.package_sizes for profile in profiles}) > 1:
        return True
    if not written.volumes_ml and len({profile.volumes_ml for profile in profiles}) > 1:
        return True
    return False


def match_single_product(
    written_product_name: str, catalog: tuple[CatalogProduct, ...]
) -> tuple[str, str | None, int | None, float | None, list[ProductMatchCandidate]]:
    """Return the existing status/name/row/score/candidates contract."""
    normalized = _normalize(written_product_name)
    exact_alias = _exact_alias_candidate(normalized, catalog)
    if exact_alias is not None:
        return "matched", exact_alias.official_name, exact_alias.row, exact_alias.score, [exact_alias]

    written, usable, conflicted = _rank_scored_products(written_product_name, catalog)
    candidates = [_candidate(item) for item in usable[:MAX_CANDIDATES]]
    conflict_candidates = [
        ProductMatchCandidate(
            official_name=item.product.official_name,
            row=item.product.row,
            score=item.name_score,
        )
        for item in conflicted[:MAX_CANDIDATES]
    ]

    if not usable:
        if conflicted:
            return "strength_conflict", None, None, None, conflict_candidates
        return "unmatched", None, None, None, []

    top = usable[0]
    family = [item for item in usable if item.name_score >= NAME_FAMILY_THRESHOLD]
    second_score = usable[1].score if len(usable) > 1 else 0.0

    if (
        (len(usable) > 1 and top.score - second_score < AMBIGUITY_MARGIN)
        or _omitted_discriminator_is_ambiguous(written, family)
    ):
        logger.debug(
            "Pharmaceutical automatic-selection decision raw=%r decision=ambiguous rows=%s",
            written_product_name,
            [item.product.row for item in usable[:MAX_CANDIDATES]],
        )
        return "ambiguous", None, None, None, candidates

    if top.score >= AUTO_MATCH_THRESHOLD and not top.form_unverifiable:
        logger.debug(
            "Pharmaceutical automatic-selection decision raw=%r decision=matched row=%s",
            written_product_name,
            top.product.row,
        )
        return "matched", top.product.official_name, top.product.row, top.score, candidates

    logger.debug(
        "Pharmaceutical automatic-selection decision raw=%r decision=fuzzy rows=%s",
        written_product_name,
        [item.product.row for item in usable[:MAX_CANDIDATES]],
    )
    return "fuzzy", None, None, None, candidates


def search_catalog_products(
    query: str, catalog: tuple[CatalogProduct, ...] | None = None
) -> list[CatalogProduct]:
    """Return catalog entries ranked by the same pharmaceutical relevance as matching."""
    catalog = catalog if catalog is not None else get_catalog_products()
    normalized = _normalize(query)
    exact = _exact_alias_candidate(normalized, catalog)
    written, usable, conflicted = _rank_scored_products(query, catalog)

    ranked = usable + [item for item in conflicted if item not in usable]
    ordered_rows = []
    if exact is not None:
        ordered_rows.append(exact.row)
    # Search is intentionally broader than automatic matching. Direct normalized
    # substrings and token prefixes make abbreviations useful without weakening the
    # auto-selection safety gates.
    for product in catalog:
        searchable = [_profile(product.official_name)]
        if product.alias:
            searchable.append(_profile(product.alias))
        if any(
            normalized and (
                normalized in profile.normalized
                or (
                    written.name_tokens
                    and all(
                        any(candidate.startswith(token) for candidate in profile.name_tokens)
                        for token in written.name_tokens
                    )
                )
            )
            for profile in searchable
        ):
            ordered_rows.append(product.row)
    ordered_rows.extend(item.product.row for item in ranked if item.name_score >= 0.35)
    unique_rows = list(dict.fromkeys(ordered_rows))
    by_row = {product.row: product for product in catalog}
    return [by_row[row] for row in unique_rows if row in by_row]


def match_products(
    products: list[ProductData], catalog: tuple[CatalogProduct, ...] | None = None
) -> list[MatchedProductData]:
    catalog = catalog if catalog is not None else get_catalog_products()
    matched: list[MatchedProductData] = []
    for product in products:
        status, official_name, row, score, candidates = match_single_product(
            product.written_product_name, catalog
        )
        matched.append(
            MatchedProductData(
                written_product_name=product.written_product_name,
                quantity=product.quantity,
                free_quantity=product.free_quantity,
                free_percentage=product.free_percentage,
                expiry_date=product.expiry_date,
                notes=product.notes,
                match_status=status,
                matched_official_name=official_name,
                matched_row=row,
                match_score=score,
                candidates=candidates,
            )
        )
    return matched


def match_order_products(
    review_order: ReviewOrderResponse, catalog: tuple[CatalogProduct, ...] | None = None
) -> MatchedOrderResponse:
    matched_products = match_products(review_order.products, catalog=catalog)
    all_products_matched = bool(matched_products) and all(
        product.match_status == "matched" for product in matched_products
    )
    return MatchedOrderResponse(
        customer=review_order.customer,
        transit=review_order.transit,
        order_title=review_order.order_title,
        price_type=review_order.price_type,
        price_type_requires_confirmation=review_order.price_type_requires_confirmation,
        products=matched_products,
        order_notes=review_order.order_notes,
        blocking_errors=review_order.blocking_errors,
        warnings=review_order.warnings,
        required_confirmations=review_order.required_confirmations,
        informational_notices=review_order.informational_notices,
        missing_information=review_order.missing_information,
        confidence_score=review_order.confidence_score,
        can_generate_excel=False,
        can_proceed_to_product_matching=review_order.can_proceed_to_product_matching,
        products_require_matching=False,
        all_products_matched=all_products_matched,
    )


def validate_manual_selection(
    row: int, official_name: str, catalog: tuple[CatalogProduct, ...] | None = None
) -> ProductMatchCandidate:
    catalog = catalog if catalog is not None else get_catalog_products()
    for product in catalog:
        if product.row == row:
            if _normalize(product.official_name) != _normalize(official_name):
                raise InvalidProductSelectionError(
                    "The provided product name does not match the catalog entry for this row."
                )
            return ProductMatchCandidate(
                official_name=product.official_name, row=product.row, score=EXACT_SCORE
            )
    raise InvalidProductSelectionError("The selected row does not exist in the current product catalog.")
