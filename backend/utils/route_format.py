"""The single authoritative formatter for customer-facing order route names.

Frontend screens consume ``order_title`` returned by the backend; they must not
reconstruct transit labels independently.
"""

import re
from typing import Literal

RouteLanguage = Literal["ar", "en"]

_ARABIC_CHARACTER = re.compile(r"[\u0600-\u06ff]")
_COMPONENT_SEPARATOR = re.compile(r"\s*[-–—|/]\s*")


def _comparison_key(value: str) -> str:
    """Normalize a title component only for duplicate comparison."""
    value = value.casefold().strip()
    value = value.translate(
        str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})
    )
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", value).strip()


def _unique_route_components(*values: str | None) -> list[str]:
    """Keep display text intact while removing normalized duplicate components."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        display = (value or "").strip()
        if not display:
            continue
        component_keys = {
            key
            for part in _COMPONENT_SEPARATOR.split(display)
            if (key := _comparison_key(part))
        }
        whole_key = _comparison_key(display)
        if whole_key in seen or (component_keys and component_keys <= seen):
            continue
        result.append(display)
        seen.update(component_keys)
        if whole_key:
            seen.add(whole_key)
    return result


def detect_route_language(
    source_location: str | None, destination_customer: str | None
) -> RouteLanguage:
    """Choose the route language when the current UI has no explicit locale field.

    Arabic customer/location text is treated as an Arabic presentation context.
    Callers with an explicit UI locale should pass it directly to
    :func:`format_order_route`.
    """
    combined = f"{source_location or ''} {destination_customer or ''}"
    return "ar" if _ARABIC_CHARACTER.search(combined) else "en"


def format_order_route(
    source_location: str | None,
    order_route: str,
    destination_customer: str | None,
    ui_language: RouteLanguage,
    governorate: str | None = None,
    area: str | None = None,
) -> str:
    """Return the canonical display title for an order route."""
    source = (source_location or "").strip()
    if order_route.strip().lower() != "transit":
        return " - ".join(_unique_route_components(source, governorate, area))

    destination = (destination_customer or "").strip()
    transit_label = "ترانزيت" if ui_language == "ar" else "Transit"
    return " - ".join(
        _unique_route_components(source, transit_label, destination, governorate, area)
    )


def canonical_transit_title(
    source_location: str | None,
    destination_customer: str | None,
    *,
    ui_language: RouteLanguage | None = None,
    governorate: str | None = None,
    area: str | None = None,
) -> str:
    """Format a transit title, inferring presentation language when necessary."""
    language = ui_language or detect_route_language(source_location, destination_customer)
    return format_order_route(
        source_location,
        "transit",
        destination_customer,
        language,
        governorate,
        area,
    )


def build_order_title(
    *,
    source_location: str | None,
    is_transit: bool,
    destination_customer: str | None = None,
    governorate: str | None = None,
    area: str | None = None,
    ui_language: RouteLanguage | None = None,
) -> str:
    """Single entry point used by rules, generation, persistence, history and email."""
    language = ui_language or detect_route_language(source_location, destination_customer)
    return format_order_route(
        source_location,
        "transit" if is_transit else "standard",
        destination_customer,
        language,
        governorate,
        area if is_transit else None,
    )
