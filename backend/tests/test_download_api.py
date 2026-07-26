"""HTTP-level tests for GET /api/orders/download/{file_id}.

GENERATED_ORDERS_DIR is monkeypatched to a temp directory — none of these tests touch
the real backend/generated_orders/ directory or the Hikma workbook.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_download_serves_the_generated_file(tmp_path):
    fake_file = tmp_path / "order_20260725_143015_a1b2c3.xlsx"
    fake_file.write_bytes(b"PK\x03\x04fake xlsx bytes")

    with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
        response = client.get("/api/orders/download/order_20260725_143015_a1b2c3.xlsx")

    assert response.status_code == 200
    assert response.content == b"PK\x03\x04fake xlsx bytes"
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_download_missing_file_returns_safe_404(tmp_path):
    with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
        response = client.get("/api/orders/download/does-not-exist.xlsx")

    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "The requested file was not found."
    assert "Traceback" not in response.text
    assert str(tmp_path) not in response.text


def test_download_blocks_directory_traversal(tmp_path):
    outside_secret = tmp_path.parent / "outside_secret.xlsx"
    outside_secret.write_bytes(b"should never be served")
    try:
        with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
            response = client.get("/api/orders/download/..%2Foutside_secret.xlsx")

        assert response.status_code in (400, 404)
        assert b"should never be served" not in response.content
    finally:
        outside_secret.unlink(missing_ok=True)


def test_download_rejects_dot_dot_identifier(tmp_path):
    # URL-encoded so the HTTP client doesn't normalize ".." away before sending — this
    # exercises resolve_generated_file_path's own traversal check directly, rather than
    # relying on client-side path normalization (which would route this to a different,
    # now-existing endpoint like GET /api/orders instead of ever reaching this one).
    with patch("services.excel_generation_service.GENERATED_ORDERS_DIR", tmp_path):
        response = client.get("/api/orders/download/%2e%2e")

    assert response.status_code == 404
