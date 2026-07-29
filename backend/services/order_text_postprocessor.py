"""Deterministic cleanup of AI-parsed pharmaceutical order lines.

The AI remains responsible for broad extraction. This layer prevents a strength token
from being silently reused as quantity and enriches product attributes using the same
catalog-aware profiles as the runtime matcher.
"""

import re
import logging

from excel.catalog_reader import CatalogUnavailableError, get_catalog_products
from models.order_models import ParsedOrderResponse
from services.business_rules_service import classify_customer_type_from_name
from services.product_matching_service import _profile, _rank_scored_products
from utils.text_normalize import normalize_product_text
from utils.location_normalize import extract_iraqi_location, normalize_governorate

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
logger = logging.getLogger(__name__)
_QUANTITY_MARKER = re.compile(
    r"(?:×|(?<!\w)x|qty|quantity|boxes?|packs?|units?|عدد|كمي[هة]|حب[هة]|علب[هة]?|كارتون|اكس)"
    r"\s*[:=]?\s*([٠-٩۰-۹\d]+)",
    re.IGNORECASE,
)
_PHARMACEUTICAL_UNIT = (
    r"mcg|mg|g|ml|iu|units?|مكغ|ميكرو\s*غرام|ملغم|ملغ|ملي\s*غرام|مغ|غرام|جرام|غم|غ|مل|ملل|وحدة"
)
_EQUAL_QUANTITY = re.compile(
    rf"=\s*([٠-٩۰-۹\d]+)(?!\s*(?:{_PHARMACEUTICAL_UNIT})\b)\s*$",
    re.IGNORECASE,
)
_POST_STRENGTH_SEPARATOR_QUANTITY = re.compile(
    rf"(?:-|/)\s*([٠-٩۰-۹\d]+)(?!\s*(?:{_PHARMACEUTICAL_UNIT})\b)\s*$",
    re.IGNORECASE,
)
_TRAILING_STRENGTH_AND_QUANTITY = re.compile(
    rf"(?:[٠-٩۰-۹\d]+(?:[.,][٠-٩۰-۹\d]+)?"
    rf"(?:\s*(?:{_PHARMACEUTICAL_UNIT}))?)\s+([٠-٩۰-۹\d]+)\s*$",
    re.IGNORECASE,
)
_FREE_QUANTITY_SUFFIX = re.compile(
    r"\+\s*([٠-٩۰-۹\d]+)(?!\s*%)\s*$",
    re.IGNORECASE,
)
_FREE_QUANTITY_MARKER = re.compile(
    r"(?:free|bonus|مجاني|مجانا|هدية)\s*[:=]?\s*([٠-٩۰-۹\d]+)\s*$",
    re.IGNORECASE,
)


def _quantity_and_product_text(line: str) -> tuple[int | None, str]:
    match = _QUANTITY_MARKER.search(line)
    if match is None:
        match = _EQUAL_QUANTITY.search(line)
    if match is None:
        match = _POST_STRENGTH_SEPARATOR_QUANTITY.search(line)
    if match is None:
        match = _TRAILING_STRENGTH_AND_QUANTITY.search(line)
        if match is not None:
            # Preserve the strength expression and remove only the final quantity.
            quantity = int(match.group(1).translate(_ARABIC_DIGITS))
            cleaned = f"{line[:match.start(1)]} {line[match.end(1):]}".strip()
            return quantity, re.sub(r"\s+", " ", cleaned)
    if match is None:
        return None, line.strip()
    quantity = int(match.group(1).translate(_ARABIC_DIGITS))
    cleaned = f"{line[:match.start()]} {line[match.end():]}".strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return quantity, cleaned


def _free_quantity_and_product_text(line: str) -> tuple[int | None, str]:
    match = _FREE_QUANTITY_SUFFIX.search(line) or _FREE_QUANTITY_MARKER.search(line)
    if match is None:
        return None, line
    free_quantity = int(match.group(1).translate(_ARABIC_DIGITS))
    cleaned = f"{line[:match.start()]} {line[match.end():]}".strip()
    return free_quantity, re.sub(r"\s+", " ", cleaned)


def _find_source_line(message: str, written_name: str) -> str | None:
    written_profile = _profile(written_name)
    normalized_written = normalize_product_text(written_name)
    for line in (item.strip() for item in message.splitlines() if item.strip()):
        normalized_line = normalize_product_text(line)
        if normalized_written and normalized_written in normalized_line:
            return line
        if written_profile.name_tokens and written_profile.name_tokens <= _profile(line).name_tokens:
            return line
    return None


def _display_strength(profile) -> str | None:
    mass_values = profile.strengths.get("mass_mg", frozenset())
    if len(mass_values) != 1:
        return None
    value = next(iter(mass_values))
    return f"{value:g} mg"


def _display_concentration(profile) -> str | None:
    if len(profile.concentrations) != 1:
        return None
    category, value = next(iter(profile.concentrations))
    if category == "percent":
        return f"{value:g}%"
    return f"{value:g} mg/ml" if category == "mass_mg_per_ml" else f"{value:g} {category}"


def postprocess_parsed_order(message: str, parsed: ParsedOrderResponse) -> ParsedOrderResponse:
    customer = parsed.customer.model_copy()
    extracted_governorate, extracted_city = extract_iraqi_location(message)
    customer.governorate = normalize_governorate(customer.governorate) or extracted_governorate
    customer.city = customer.city or extracted_city
    classified = classify_customer_type_from_name(customer.customer_name)
    if classified != "unknown":
        customer.customer_type = classified

    try:
        catalog = get_catalog_products()
    except CatalogUnavailableError:
        catalog = ()

    products = []
    for product in parsed.products:
        source_line = _find_source_line(message, product.written_product_name)
        explicit_quantity = None
        explicit_free_quantity = None
        product_text = product.written_product_name
        if source_line:
            explicit_free_quantity, without_free = _free_quantity_and_product_text(source_line)
            explicit_quantity, product_text = _quantity_and_product_text(without_free)

        profile = _profile(product_text)
        if catalog:
            profile, _usable, _conflicted = _rank_scored_products(product_text, catalog)

        recognized_strength = _display_strength(profile)
        quantity = explicit_quantity if explicit_quantity is not None else product.quantity
        logger.debug(
            "Order-line parse trace raw=%r normalized=%r numeric_tokens=%s "
            "strength=%s concentration=%s forms=%s package=%s explicit_quantity=%s",
            source_line or product.written_product_name,
            normalize_product_text(product_text),
            re.findall(r"\d+(?:\.\d+)?", normalize_product_text(product_text)),
            recognized_strength,
            _display_concentration(profile),
            sorted(profile.forms),
            sorted(profile.package_sizes),
            explicit_quantity,
        )

        # A quantity in the source message must have quantity context. Do not retain an
        # AI-inferred number merely because it differs from the strength (for example,
        # treating "Vanco 0.5" as quantity 20). Explicit marker extraction above remains
        # authoritative and is always preserved.
        if (
            source_line is not None
            and explicit_quantity is None
            and recognized_strength
            and quantity is not None
        ):
            quantity = None

        products.append(
            product.model_copy(
                update={
                    "written_product_name": (
                        product_text
                        if recognized_strength or explicit_quantity is not None
                        else product.written_product_name
                    ),
                    "strength": recognized_strength or product.strength,
                    "concentration": _display_concentration(profile) or product.concentration,
                    "dosage_form": " / ".join(sorted(profile.forms)) or product.dosage_form,
                    "package_size": (
                        " / ".join(f"{count} {form}" for form, count in sorted(profile.package_sizes))
                        or product.package_size
                    ),
                    "quantity": quantity,
                    "free_quantity": (
                        explicit_free_quantity
                        if explicit_free_quantity is not None
                        else product.free_quantity
                    ),
                }
            )
        )

    transit = parsed.transit.model_copy()
    if transit.is_transit:
        transit.destination_governorate = (
            normalize_governorate(transit.destination_governorate)
            or customer.governorate
            or extracted_governorate
        )
        transit.destination_city = transit.destination_city or customer.city or extracted_city
        transit.destination_area = transit.destination_area or customer.area
        customer.governorate = transit.destination_governorate
        customer.city = transit.destination_city
        customer.area = transit.destination_area or customer.area

    logger.debug(
        "Location parse trace raw_message=%r governorate=%r city=%r area=%r "
        "source_customer=%r destination_customer=%r destination_governorate=%r",
        message,
        customer.governorate,
        customer.city,
        customer.area,
        transit.primary_customer,
        transit.destination_customer,
        transit.destination_governorate,
    )
    return parsed.model_copy(update={"customer": customer, "transit": transit, "products": products})
