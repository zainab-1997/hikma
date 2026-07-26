"""Deployment checks use temporary storage and never touch app.db or the source workbook."""

import hashlib
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from config.settings import Settings
from database.session import get_engine, init_db
from main import create_app
from scripts.cleanup_generated_orders import cleanup_generated_orders
from services import startup_validation_service
from services.startup_validation_service import readiness_status, validate_startup


def deployment_settings(tmp_path: Path, **overrides) -> Settings:
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"read-only fixture")
    defaults = {
        "app_env": "test",
        "app_allowed_hosts": "testserver,localhost",
        "cors_allowed_origins": "http://localhost:5173",
        "database_url": f"sqlite:///{tmp_path / 'app.db'}",
        "excel_template_path": str(template),
        "generated_orders_dir": str(tmp_path / "generated"),
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_development_startup_configuration_passes(tmp_path):
    settings = deployment_settings(tmp_path, app_env="development")
    assert validate_startup(settings).ready


def test_production_debug_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="APP_DEBUG"):
        deployment_settings(
            tmp_path, app_env="production", app_debug=True,
            app_allowed_hosts="orders.example.invalid",
            cors_allowed_origins="https://orders.example.invalid",
        )


def test_production_wildcard_cors_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="wildcard"):
        deployment_settings(
            tmp_path, app_env="production", app_allowed_hosts="orders.example.invalid",
            cors_allowed_origins="*",
        )


def test_production_http_cors_origin_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="HTTPS origins"):
        deployment_settings(
            tmp_path,
            app_env="production",
            app_allowed_hosts="orders.example.invalid",
            cors_allowed_origins="http://orders.example.invalid",
        )


def test_production_local_or_test_hosts_are_rejected(tmp_path):
    with pytest.raises(ValidationError, match="public hostnames"):
        deployment_settings(
            tmp_path,
            app_env="production",
            app_allowed_hosts="orders.example.invalid,testserver",
            cors_allowed_origins="https://orders.example.invalid",
        )


def test_csv_configuration_is_trimmed_deduplicated_and_safe(tmp_path):
    settings = deployment_settings(
        tmp_path,
        cors_allowed_origins=" https://a.example,https://b.example,https://a.example ",
        app_allowed_hosts="a.example, b.example",
    )
    assert settings.allowed_origins_list == ["https://a.example", "https://b.example"]
    assert settings.allowed_hosts_list == ["a.example", "b.example"]


def test_missing_template_fails_readiness(tmp_path):
    settings = deployment_settings(tmp_path, excel_template_path=str(tmp_path / "missing.xlsx"))
    assert readiness_status(settings).template == "unavailable"


def test_unwritable_generated_directory_fails_readiness(tmp_path, monkeypatch):
    settings = deployment_settings(tmp_path)
    monkeypatch.setattr(startup_validation_service, "_directory_writable", lambda *_args, **_kwargs: False)
    assert readiness_status(settings).generated_orders == "unavailable"


def test_database_failure_is_safe(tmp_path, monkeypatch):
    settings = deployment_settings(tmp_path)
    monkeypatch.setattr(startup_validation_service, "check_database", lambda *_args: (_ for _ in ()).throw(OSError()))
    assert readiness_status(settings).database == "unavailable"


def test_health_liveness_and_readiness_success(tmp_path):
    app = create_app(deployment_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/health/live").json() == {"status": "ok"}
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_health_readiness_failure_is_non_200_and_exposes_no_paths(tmp_path):
    settings = deployment_settings(tmp_path, excel_template_path=str(tmp_path / "private" / "missing.xlsx"))
    client = TestClient(create_app(settings))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert str(tmp_path) not in response.text
    assert "sqlite:///" not in response.text
    assert "smtp" not in response.text.lower()


def test_request_id_generated_preserved_and_invalid_replaced(tmp_path):
    client = TestClient(create_app(deployment_settings(tmp_path)))
    generated = client.get("/api/health/live").headers["x-request-id"]
    assert generated
    preserved = client.get("/api/health/live", headers={"X-Request-ID": "safe-request_123"})
    assert preserved.headers["x-request-id"] == "safe-request_123"
    replaced = client.get("/api/health/live", headers={"X-Request-ID": "unsafe request/id"})
    assert replaced.headers["x-request-id"] != "unsafe request/id"


def test_unhandled_error_is_generic_with_request_id_and_no_traceback(tmp_path):
    app = create_app(deployment_settings(tmp_path))

    @app.get("/test-error")
    def test_error():
        raise RuntimeError("private internal detail")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-error", headers={"X-Request-ID": "error-123"})
    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected server error occurred.",
        "request_id": "error-123",
    }
    assert response.headers["x-request-id"] == "error-123"
    assert "RuntimeError" not in response.text
    assert "private internal detail" not in response.text


def test_sqlite_foreign_keys_and_busy_timeout(tmp_path):
    url = f"sqlite:///{tmp_path / 'pragma.db'}"
    init_db(url)
    with get_engine(url).connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000


def test_cleanup_is_dry_run_by_default_and_respects_age(tmp_path):
    generated = tmp_path / "generated"
    generated.mkdir()
    old_file = generated / "old.xlsx"
    new_file = generated / "new.xlsx"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")
    now = time.time()
    os.utime(old_file, (now - 40 * 86400, now - 40 * 86400))
    result = cleanup_generated_orders(generated, retention_days=30, now=now)
    assert result.eligible == (old_file,)
    assert old_file.exists()
    assert new_file.exists()
    assert result.deleted == ()


def test_cleanup_cannot_escape_and_never_selects_template(tmp_path):
    generated = tmp_path / "generated"
    generated.mkdir()
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"outside")
    link = generated / "escape.xlsx"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    template = generated / "template.xlsx"
    template.write_bytes(b"template")
    old = time.time() - 40 * 86400
    os.utime(template, (old, old))
    result = cleanup_generated_orders(
        generated, retention_days=30, execute=True, template_path=template, now=time.time()
    )
    assert not result.deleted
    assert outside.exists()
    assert template.exists()


def test_source_workbook_hash_unchanged():
    workbook = Path(__file__).parents[1] / "templates" / "Hikma orders.xlsx"
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == (
        "730edb4229048a7b7ff6b593749e7b507cfd547936fe7b306637869636f119c8"
    )
