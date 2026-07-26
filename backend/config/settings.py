"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hikma Order Automation"
    app_version: str = "1.0.0-rc1"
    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = False
    app_log_level: str = "INFO"
    app_allowed_hosts: str = "localhost,127.0.0.1,testserver"

    ai_provider: Literal["openai", "groq"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"

    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "sqlite:///./database/app.db"
    generated_orders_dir: str = "generated_orders"
    excel_template_path: str = "templates/Hikma orders.xlsx"
    max_upload_size_mb: int = 10
    request_timeout_seconds: int = 30
    trusted_proxy_count: int = 0
    generated_file_retention_days: int = 30

    # Email delivery is off by default. Sending only ever runs when a user explicitly
    # clicks Send Email on an already-generated order — see services/email_delivery_service.py.
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 20
    email_from_address: str = ""
    email_from_name: str = "Hikma Orders"
    default_order_recipients: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        return self._csv(self.cors_allowed_origins)

    @property
    def allowed_hosts_list(self) -> list[str]:
        return self._csv(self.app_allowed_hosts)

    @property
    def default_order_recipients_list(self) -> list[str]:
        return self._csv(self.default_order_recipients)

    @staticmethod
    def _csv(value: str) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))

    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("APP_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator(
        "app_port", "max_upload_size_mb", "request_timeout_seconds", "generated_file_retention_days"
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be greater than zero")
        return value

    @field_validator("trusted_proxy_count")
    @classmethod
    def validate_proxy_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("TRUSTED_PROXY_COUNT cannot be negative")
        return value

    @model_validator(mode="after")
    def validate_environment_safety(self):
        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in production")
            if "*" in self.allowed_origins_list:
                raise ValueError("wildcard CORS origins are not allowed in production")
            if not self.allowed_origins_list:
                raise ValueError("CORS_ALLOWED_ORIGINS is required in production")
            if "*" in self.allowed_hosts_list or not self.allowed_hosts_list:
                raise ValueError("explicit APP_ALLOWED_HOSTS values are required in production")
            for origin in self.allowed_origins_list:
                parsed = urlsplit(origin)
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.path not in ("", "/")
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(
                        "production CORS_ALLOWED_ORIGINS must contain HTTPS origins only"
                    )
            local_hosts = {"localhost", "127.0.0.1", "::1", "testserver"}
            if any(host.lower().split(":", 1)[0] in local_hosts for host in self.allowed_hosts_list):
                raise ValueError(
                    "production APP_ALLOWED_HOSTS must contain public hostnames only"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
