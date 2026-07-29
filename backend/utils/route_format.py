"""The single authoritative formatter for customer-facing order route names.

Frontend screens consume ``order_title`` returned by the backend; they must not
reconstruct transit labels independently.
"""

import re
from typing import Literal

RouteLanguage = Literal["ar", "en"]

_ARABIC_CHARACTER = re.compile(r"[\u0600-\u06ff]")


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
    locations = [item.strip() for item in (governorate, area) if item and item.strip()]
    if order_route.strip().lower() != "transit":
        return " - ".join([source, *locations])

    destination = (destination_customer or "").strip()
    transit_label = "ترانزيت" if ui_language == "ar" else "Transit"
    return " - ".join([source, transit_label, destination, *locations])


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
