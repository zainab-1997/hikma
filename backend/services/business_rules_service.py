"""Deterministic business rules that turn a parsed order into a review-ready order.

No AI is used anywhere in this module. The AI parser understands the message;
this layer makes the company's pricing, title, and validation decisions.
"""

import math
import re

from models.order_models import CustomerType, ProductData, TransitData
from models.review_order_models import (
    ApplyRulesRequest,
    PriceType,
    ReviewOrderResponse,
    RuleConfirmation,
    RuleWarning,
)

_PRICE_TYPE_BY_CUSTOMER_TYPE: dict[CustomerType, tuple[PriceType, bool]] = {
    "pharmacy": ("pharmacy", False),
    "hospital": ("pharmacy", False),
    "drug_store": ("drug_store", False),
    "office": ("unknown", True),
    "unknown": ("unknown", True),
}

_OPTIONAL_FIELD_LABELS = {
    "governorate": "Governorate",
    "area": "Area",
    "phone_number": "Phone number",
    "address": "Address",
    "notes": "Notes",
    "contact_person": "Contact person",
}


def classify_customer_type_from_name(name: str | None) -> CustomerType:
    """Classify a customer name using the same name-prefix rules given to the AI parser."""
    if not name:
        return "unknown"

    stripped = name.strip()
    if stripped.startswith("صيدلية"):
        return "pharmacy"
    if stripped.startswith("مستشفى"):
        return "hospital"
    if stripped.startswith("مذخر"):
        return "drug_store"
    if stripped.startswith("مكتب"):
        return "office"
    return "unknown"


def _add_missing(missing_information: list[str], item: str) -> None:
    if item not in missing_information:
        missing_information.append(item)


def _canonical_field(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    normalized = re.sub(r"^(missing_|no_)", "", normalized)
    normalized = re.sub(r"(_is)?_missing$", "", normalized)
    normalized = re.sub(r"_not_(provided|specified|available)$", "", normalized)
    aliases = {
        "phone": "phone_number",
        "telephone": "phone_number",
        "mobile": "phone_number",
        "order_notes": "notes",
        "note": "notes",
        "mentioned_people": "contact_person",
        "contact": "contact_person",
        "customer": "customer_name",
        "customer_identifier": "customer_name",
        "product": "product_name",
    }
    return aliases.get(normalized, normalized)


def _dedupe_rule_items(items):
    seen: set[tuple[str, str]] = set()
    result = []
    for item in items:
        field = _canonical_field(str((item.details or {}).get("field", item.type)))
        message = re.sub(r"\s+", " ", item.message.strip().lower())
        key = (field, message)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _optional_notice(field: str) -> RuleWarning:
    return RuleWarning(
        type="optional_information_missing",
        message=f"Optional information not provided: {_OPTIONAL_FIELD_LABELS[field]}.",
        details={"field": field},
    )


def _resolve_transit_parties(
    transit: TransitData,
) -> tuple[str | None, str | None, CustomerType, CustomerType, bool]:
    """Resolve which transit party is the primary (paying) customer.

    Returns (primary_customer, destination_customer, primary_type, destination_type, ambiguous).
    The parser is instructed not to reorder parties, so this is the only place that may
    normalize them, and only when the roles are unambiguous from name-prefix classification.
    """
    primary_type = classify_customer_type_from_name(transit.primary_customer)
    destination_type = classify_customer_type_from_name(transit.destination_customer)

    primary_customer = transit.primary_customer
    destination_customer = transit.destination_customer

    if primary_type == "unknown" or destination_type == "unknown":
        return primary_customer, destination_customer, primary_type, destination_type, True

    if primary_type == destination_type:
        return primary_customer, destination_customer, primary_type, destination_type, True

    if primary_type == "pharmacy" and destination_type == "drug_store":
        # A drug store is virtually always the company's direct (primary) customer in a
        # transit chain, with the pharmacy as the final destination. Swap when the parser
        # captured them in the reversed, literal message order.
        primary_customer, destination_customer = destination_customer, primary_customer
        primary_type, destination_type = destination_type, primary_type

    return primary_customer, destination_customer, primary_type, destination_type, False


def _office_confirmation() -> RuleConfirmation:
    return RuleConfirmation(
        type="office_price_type",
        message=(
            "This is an office customer. Select whether Pharmacy Price or "
            "Drug Store Price applies to this order."
        ),
        details={"options": ["pharmacy", "drug_store"]},
    )


def _unknown_customer_confirmation() -> RuleConfirmation:
    return RuleConfirmation(
        type="customer_type_or_price_type",
        message="The customer type could not be determined. Confirm the customer type or price type.",
    )


def _build_order_title(transit: TransitData, customer_name: str | None, governorate: str | None) -> str:
    if transit.is_transit:
        primary = transit.primary_customer or "Unknown"
        destination = transit.destination_customer or "Unknown"
        title = f"{primary} - Transit - {destination}"
        if governorate:
            title = f"{title} - {governorate}"
        return title

    name = customer_name or "Unknown Customer"
    if governorate:
        return f"{name} - {governorate}"
    return name


def _process_products(
    products: list[ProductData],
) -> tuple[
    list[ProductData],
    list[RuleWarning],
    list[RuleWarning],
    list[RuleConfirmation],
    list[str],
]:
    resolved_products: list[ProductData] = []
    blocking_errors: list[RuleWarning] = []
    warnings: list[RuleWarning] = []
    confirmations: list[RuleConfirmation] = []
    missing_information: list[str] = []

    name_counts: dict[str, int] = {}
    for product in products:
        name = (product.written_product_name or "").strip()
        name_counts[name] = name_counts.get(name, 0) + 1

    flagged_duplicate_names: set[str] = set()

    for product in products:
        name = (product.written_product_name or "").strip()

        if not name:
            _add_missing(missing_information, "product_name")
            blocking_errors.append(
                RuleWarning(
                    type="invalid_product_name",
                    message="A product line is missing a product name.",
                    details={"field": "product_name", "quantity": product.quantity},
                )
            )

        if product.quantity <= 0:
            _add_missing(missing_information, "quantity")
            details = {"product_name": name or None, "quantity": product.quantity}
            blocking_errors.append(
                RuleWarning(
                    type="invalid_quantity",
                    message=f'Product "{name or "unnamed"}" has an invalid quantity ({product.quantity}).',
                    details={**details, "field": "quantity"},
                )
            )
            confirmations.append(
                RuleConfirmation(
                    type="invalid_quantity",
                    message=f'Confirm the correct quantity for "{name or "unnamed"}".',
                    details=details,
                )
            )

        resolved_free_quantity = product.free_quantity

        if product.free_percentage is not None:
            exact_free_quantity = product.quantity * product.free_percentage / 100
            rounded_free_quantity = round(exact_free_quantity)

            if math.isclose(exact_free_quantity, rounded_free_quantity, rel_tol=0, abs_tol=1e-9):
                resolved_free_quantity = int(rounded_free_quantity)
            else:
                # Do not silently round — leave free_quantity unresolved and surface the
                # calculation for the user to confirm instead.
                details = {
                    "product_name": name or None,
                    "calculated_free_quantity": exact_free_quantity,
                    "suggested_free_quantity": rounded_free_quantity,
                }
                blocking_errors.append(
                    RuleWarning(
                        type="non_integer_free_quantity",
                        message=(
                            f'The calculated free quantity for "{name or "unnamed"}" '
                            f"is not a whole number ({exact_free_quantity})."
                        ),
                        details={**details, "field": "free_quantity"},
                    )
                )
                confirmations.append(
                    RuleConfirmation(
                        type="non_integer_free_quantity",
                        message=(
                            f'Confirm the free quantity for "{name or "unnamed"}" — calculated '
                            f"{exact_free_quantity}, suggested {rounded_free_quantity}."
                        ),
                        details=details,
                    )
                )

        resolved_products.append(
            ProductData(
                written_product_name=product.written_product_name,
                quantity=product.quantity,
                free_quantity=resolved_free_quantity,
                free_percentage=product.free_percentage,
                expiry_date=product.expiry_date,
                notes=product.notes,
            )
        )

        if name and name_counts[name] > 1:
            flagged_duplicate_names.add(name)

    for duplicate_name in flagged_duplicate_names:
        occurrences = [
            {"quantity": p.quantity, "free_quantity": p.free_quantity, "free_percentage": p.free_percentage}
            for p in products
            if (p.written_product_name or "").strip() == duplicate_name
        ]
        blocking_errors.append(
            RuleWarning(
                type="duplicate_product",
                message=f'Product "{duplicate_name}" appears more than once in the order.',
                details={
                    "field": "product_name",
                    "product_name": duplicate_name,
                    "occurrences": occurrences,
                },
            )
        )

    return resolved_products, blocking_errors, warnings, confirmations, missing_information


def apply_business_rules(request: ApplyRulesRequest) -> ReviewOrderResponse:
    blocking_errors: list[RuleWarning] = []
    warnings: list[RuleWarning] = []
    confirmations: list[RuleConfirmation] = []
    informational_notices: list[RuleWarning] = []
    missing_information: list[str] = []

    customer = request.customer.model_copy()
    transit = request.transit.model_copy()
    ambiguous_transit = False

    if transit.is_transit:
        primary_customer, destination_customer, primary_type, destination_type, ambiguous_transit = (
            _resolve_transit_parties(transit)
        )
        transit = TransitData(
            is_transit=True,
            primary_customer=primary_customer,
            destination_customer=destination_customer,
            destination_type=destination_type,
        )

        if not primary_customer:
            _add_missing(missing_information, "primary_customer")
            blocking_errors.append(
                RuleWarning(
                    type="missing_required_field",
                    message="Transit primary customer is required.",
                    details={"field": "primary_customer"},
                )
            )
        if not destination_customer:
            _add_missing(missing_information, "destination_customer")
            blocking_errors.append(
                RuleWarning(
                    type="missing_required_field",
                    message="Transit destination customer is required.",
                    details={"field": "destination_customer"},
                )
            )

        customer = customer.model_copy(
            update={
                "customer_name": primary_customer or customer.customer_name,
                "customer_type": primary_type,
            }
        )

        if ambiguous_transit:
            confirmations.append(
                RuleConfirmation(
                    type="ambiguous_transit_parties",
                    message=(
                        "Unable to confidently determine which transit party is the primary "
                        "(paying) customer. Please confirm the primary and destination customers."
                    ),
                    details={
                        "primary_customer": primary_customer,
                        "destination_customer": destination_customer,
                    },
                )
            )
            price_type: PriceType = "unknown"
            price_type_requires_confirmation = True
        else:
            price_type, price_type_requires_confirmation = _PRICE_TYPE_BY_CUSTOMER_TYPE[primary_type]
    else:
        if not customer.customer_name:
            _add_missing(missing_information, "customer_name")
            blocking_errors.append(
                RuleWarning(
                    type="missing_required_field",
                    message="Customer name or identifier is required.",
                    details={"field": "customer_name"},
                )
            )
        price_type, price_type_requires_confirmation = _PRICE_TYPE_BY_CUSTOMER_TYPE[customer.customer_type]

    if price_type_requires_confirmation and not ambiguous_transit:
        if request.price_type_override is not None:
            price_type = request.price_type_override
            price_type_requires_confirmation = False
        elif customer.customer_type == "office":
            confirmations.append(_office_confirmation())
        else:
            confirmations.append(_unknown_customer_confirmation())

    optional_values = {
        "governorate": customer.governorate,
        "area": customer.area,
        "phone_number": customer.phone_number,
    }
    for field, value in optional_values.items():
        if not value:
            informational_notices.append(_optional_notice(field))
    for parser_item in request.missing_information:
        field = _canonical_field(parser_item)
        if field in _OPTIONAL_FIELD_LABELS:
            informational_notices.append(_optional_notice(field))
        elif field not in {
            "customer_name",
            "product_name",
            "products",
            "quantity",
            "customer_type",
            "price_type",
            "primary_customer",
            "destination_customer",
        }:
            informational_notices.append(
                RuleWarning(
                    type="parser_information_missing",
                    message=f"Information not provided: {parser_item.strip().rstrip('.')}.",
                    details={"field": field or "unspecified"},
                )
            )

    order_title = _build_order_title(transit, customer.customer_name, customer.governorate)

    if not request.products:
        _add_missing(missing_information, "products")
        blocking_errors.append(
            RuleWarning(
                type="missing_required_field",
                message="At least one product is required.",
                details={"field": "products"},
            )
        )

    (
        products,
        product_blocking_errors,
        product_warnings,
        product_confirmations,
        product_missing,
    ) = _process_products(request.products)
    blocking_errors.extend(product_blocking_errors)
    warnings.extend(product_warnings)
    confirmations.extend(product_confirmations)
    for item in product_missing:
        _add_missing(missing_information, item)

    can_proceed_to_product_matching = (
        not confirmations and not blocking_errors and not missing_information
    )

    return ReviewOrderResponse(
        customer=customer,
        transit=transit,
        order_title=order_title,
        price_type=price_type,
        price_type_requires_confirmation=price_type_requires_confirmation,
        products=products,
        order_notes=list(request.order_notes),
        blocking_errors=_dedupe_rule_items(blocking_errors),
        warnings=_dedupe_rule_items(warnings),
        required_confirmations=_dedupe_rule_items(confirmations),
        informational_notices=_dedupe_rule_items(informational_notices),
        missing_information=missing_information,
        confidence_score=request.confidence_score,
        can_generate_excel=False,
        can_proceed_to_product_matching=can_proceed_to_product_matching,
        products_require_matching=True,
    )
