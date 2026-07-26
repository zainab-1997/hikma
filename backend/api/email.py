"""Non-secret email configuration exposed to the frontend.

Never returns SMTP host, port, username, or password — only what the UI needs to show
the user which recipients an order will go to before they click Send.
"""

from fastapi import APIRouter

from config.settings import get_settings
from models.email_models import EmailConfigResponse

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/config", response_model=EmailConfigResponse)
def get_email_config() -> EmailConfigResponse:
    settings = get_settings()
    return EmailConfigResponse(
        email_enabled=settings.email_enabled,
        default_recipients=settings.default_order_recipients_list,
        from_name=settings.email_from_name,
    )
