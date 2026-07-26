"""Turn a WhatsApp order message into structured data using the selected AI provider.

Both providers use the OpenAI Python SDK's structured chat-completion parser. Groq is
accessed through its OpenAI-compatible base URL, keeping the response validation and
the public parser contract identical across providers.
"""

import logging
from dataclasses import dataclass

from openai import OpenAI, OpenAIError

from config.settings import Settings
from config.settings import get_settings
from models.order_models import ParsedOrderResponse
from prompts.whatsapp_parser_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OrderParsingError(Exception):
    """Base error raised when a WhatsApp order message could not be parsed."""

    status_code = 502


class ParserNotConfiguredError(OrderParsingError):
    """Raised when the AI parser is missing required configuration (e.g. API key)."""

    status_code = 503


class ParserResponseInvalidError(OrderParsingError):
    """Raised when the AI response does not match the expected structured schema."""

    status_code = 502


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    model: str
    base_url: str | None = None


def _provider_config(settings: Settings) -> ProviderConfig:
    if settings.ai_provider == "groq":
        return ProviderConfig(
            name="groq",
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
        )
    return ProviderConfig(
        name="openai",
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def parse_whatsapp_order(message: str) -> ParsedOrderResponse:
    settings = get_settings()
    provider = _provider_config(settings)

    if not provider.api_key:
        raise ParserNotConfiguredError("The AI parsing service is not configured.")

    client_kwargs = {"api_key": provider.api_key}
    if provider.base_url:
        client_kwargs["base_url"] = provider.base_url
    client = OpenAI(**client_kwargs)

    try:
        completion = client.chat.completions.parse(
            model=provider.model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            response_format=ParsedOrderResponse,
        )
    except OpenAIError as exc:
        logger.error("AI parser request failed for provider %s.", provider.name)
        raise OrderParsingError("The AI parsing service failed to respond.") from exc

    choice = completion.choices[0]

    if choice.message.refusal:
        logger.error("AI provider %s refused to parse the order message.", provider.name)
        raise ParserResponseInvalidError("The AI declined to parse this message.")

    parsed = choice.message.parsed
    if parsed is None:
        logger.error(
            "AI provider %s returned a response that failed schema validation.",
            provider.name,
        )
        raise ParserResponseInvalidError("The AI response did not match the expected format.")

    return parsed
