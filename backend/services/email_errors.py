"""Shared exception hierarchy for the email-delivery layer.

Every message is safe to return to an API client as-is: no SMTP credentials, no
filesystem paths, no raw provider responses, no stack traces.
"""


class EmailDeliveryError(Exception):
    status_code = 500


class EmailConfigurationError(EmailDeliveryError):
    """Email sending is disabled or SMTP settings are incomplete/invalid."""

    status_code = 503


class OrderNotFoundForEmailError(EmailDeliveryError):
    status_code = 404


class GeneratedFileMissingError(EmailDeliveryError):
    status_code = 404


class RecipientValidationError(EmailDeliveryError):
    status_code = 422


class EmailContentError(EmailDeliveryError):
    status_code = 422


class EmailRequestIdConflictError(EmailDeliveryError):
    """The same email_request_id was already used for a different order."""

    status_code = 409


class EmailRecordingError(EmailDeliveryError):
    """The email attempt could not be durably recorded. See the docstring on
    services.email_delivery_service.send_order_email for what this means for the
    delivery's actual (unknown) outcome."""

    status_code = 500
