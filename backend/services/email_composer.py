"""Builds the outgoing email message (plain-text + HTML bodies, subject, attachment) for
a saved order.

Every user-controlled value — the optional message, and anything that ends up in a
header (subject override, addresses) — is defended against header injection and, for the
HTML body, escaped before insertion. The frontend can never supply raw HTML: the message
is always treated as plain text and escaped. Only fields already present on the saved
Order row are used — no parser confidence score, no internal row numbers, no filesystem
paths, ever end up in the email.
"""

import html
import re
from email.message import EmailMessage
from email.utils import formataddr

from services.email_errors import EmailContentError

_HEADER_INJECTION_PATTERN = re.compile(r"[\r\n]")
MAX_MESSAGE_LENGTH = 2000
MAX_SUBJECT_LENGTH = 200


def reject_header_injection(value: str, field_name: str) -> str:
    if _HEADER_INJECTION_PATTERN.search(value):
        raise EmailContentError(f"{field_name} must not contain line breaks.")
    return value


def _format_price_type(price_type: str) -> str:
    if price_type == "pharmacy":
        return "Pharmacy Price"
    if price_type == "drug_store":
        return "Drug Store Price"
    return "Unknown"


def build_subject(order, override: str | None) -> str:
    if override and override.strip():
        subject = reject_header_injection(override.strip(), "subject")
        return subject[:MAX_SUBJECT_LENGTH]
    label = order.customer_name or order.order_title
    return f"Hikma Order {order.order_number} - {label}"[:MAX_SUBJECT_LENGTH]


def _summary_rows(order) -> list[tuple[str, str]]:
    rows = [
        ("Order Number", order.order_number),
        ("Customer/Order Title", order.order_title),
    ]
    if order.governorate:
        rows.append(("Governorate", order.governorate))
    rows.append(("Price Type", _format_price_type(order.selected_price_type)))
    rows.append(("Order Total", f"{order.selected_order_total:,}"))
    rows.append(("Generated File", order.generated_filename))
    rows.append(("Created", order.created_at.isoformat()))
    return rows


def build_plain_text_body(order, message: str | None) -> str:
    lines = [f"{label}: {value}" for label, value in _summary_rows(order)]
    if message:
        lines.append("")
        lines.append("Message:")
        lines.append(message)
    return "\n".join(lines)


def build_html_body(order, message: str | None) -> str:
    rows_html = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#64748b;'>{html.escape(label)}</td>"
        f"<td style='padding:4px 0;font-weight:600;color:#0f172a;'>{html.escape(str(value))}</td></tr>"
        for label, value in _summary_rows(order)
    )

    message_html = ""
    if message:
        escaped_message = html.escape(message).replace("\n", "<br>")
        message_html = f"<p style='margin-top:16px;color:#1f2937;'>{escaped_message}</p>"

    return (
        "<html><body style='font-family:sans-serif;'>"
        "<h2 style='color:#0f172a;'>Hikma Order Automation</h2>"
        f"<table>{rows_html}</table>"
        f"{message_html}"
        "</body></html>"
    )


def build_email_message(
    *,
    order,
    from_address: str,
    from_name: str,
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    message: str | None,
    attachment_path,
    attachment_filename: str,
) -> EmailMessage:
    reject_header_injection(from_name, "sender display name")
    for address in [*to_addresses, *cc_addresses]:
        reject_header_injection(address, "recipient address")

    email_message = EmailMessage()
    email_message["Subject"] = subject
    email_message["From"] = formataddr((from_name, from_address))
    email_message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        email_message["Cc"] = ", ".join(cc_addresses)

    email_message.set_content(build_plain_text_body(order, message))
    email_message.add_alternative(build_html_body(order, message), subtype="html")

    with open(attachment_path, "rb") as handle:
        attachment_bytes = handle.read()

    email_message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=attachment_filename,
    )

    return email_message
