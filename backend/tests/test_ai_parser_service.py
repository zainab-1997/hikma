"""Provider-selection tests for the structured WhatsApp order parser.

No test contacts OpenAI or Groq. The shared OpenAI SDK client is always mocked.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from config.settings import Settings
from main import app
from models.order_models import CustomerData, ParsedOrderResponse, ProductData, TransitData
from services.ai_parser_service import ParserNotConfiguredError, parse_whatsapp_order


MESSAGE = "صيدلية الاختبار\nاتكيور ٢٠"


def _parsed_response() -> ParsedOrderResponse:
    return ParsedOrderResponse(
        customer=CustomerData(customer_name="صيدلية الاختبار", customer_type="pharmacy"),
        transit=TransitData(),
        products=[ProductData(written_product_name="اتكيور", quantity=20)],
        confidence_score=0.98,
    )


def _completion():
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(refusal=None, parsed=_parsed_response()))]
    )


def _mock_client(completion=None, error=None):
    client = Mock()
    if error is not None:
        client.chat.completions.parse.side_effect = error
    else:
        client.chat.completions.parse.return_value = completion or _completion()
    return client


def test_groq_provider_selection_and_base_url():
    settings = Settings(
        _env_file=None,
        ai_provider="groq",
        groq_api_key="test-groq-key",
        groq_model="openai/gpt-oss-120b",
    )
    client = _mock_client()

    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch("services.ai_parser_service.OpenAI", return_value=client) as openai_client,
    ):
        result = parse_whatsapp_order(MESSAGE)

    openai_client.assert_called_once_with(
        api_key="test-groq-key",
        base_url="https://api.groq.com/openai/v1",
    )
    call = client.chat.completions.parse.call_args.kwargs
    assert call["model"] == "openai/gpt-oss-120b"
    assert call["temperature"] == 0
    assert call["response_format"] is ParsedOrderResponse
    assert result == _parsed_response()


def test_custom_groq_base_url_is_used():
    settings = Settings(
        _env_file=None,
        ai_provider="groq",
        groq_api_key="test-groq-key",
        groq_base_url="https://groq-proxy.example.invalid/openai/v1",
        groq_model="configured-model",
    )

    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch("services.ai_parser_service.OpenAI", return_value=_mock_client()) as openai_client,
    ):
        parse_whatsapp_order(MESSAGE)

    assert openai_client.call_args.kwargs["base_url"] == (
        "https://groq-proxy.example.invalid/openai/v1"
    )


def test_missing_groq_key_fails_before_client_creation():
    settings = Settings(_env_file=None, ai_provider="groq", groq_api_key="")

    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch("services.ai_parser_service.OpenAI") as openai_client,
        pytest.raises(ParserNotConfiguredError, match="not configured"),
    ):
        parse_whatsapp_order(MESSAGE)

    openai_client.assert_not_called()


def test_openai_provider_still_uses_existing_client_configuration():
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="test-openai-key",
        openai_model="gpt-4.1-mini",
    )
    client = _mock_client()

    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch("services.ai_parser_service.OpenAI", return_value=client) as openai_client,
    ):
        result = parse_whatsapp_order(MESSAGE)

    openai_client.assert_called_once_with(api_key="test-openai-key")
    assert client.chat.completions.parse.call_args.kwargs["model"] == "gpt-4.1-mini"
    assert result == _parsed_response()


def test_provider_secret_is_absent_from_response_and_logs(caplog):
    secret = "groq-secret-must-not-leak"
    settings = Settings(
        _env_file=None,
        ai_provider="groq",
        groq_api_key=secret,
        groq_model="openai/gpt-oss-120b",
    )
    client = _mock_client(error=OpenAIError(f"provider failure containing {secret}"))

    with (
        patch("services.ai_parser_service.get_settings", return_value=settings),
        patch("services.ai_parser_service.OpenAI", return_value=client),
    ):
        response = TestClient(app).post("/api/orders/parse", json={"message": MESSAGE})

    assert response.status_code == 502
    assert response.json()["detail"] == "The AI parsing service failed to respond."
    assert secret not in response.text
    assert secret not in caplog.text
    assert "GROQ_API_KEY" not in response.text
    assert "GROQ_API_KEY" not in caplog.text
