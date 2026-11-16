import importlib

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.routers.wardrobe import database_path


@pytest.fixture(autouse=True)
def isolated_startup_database(tmp_path):
    app = importlib.import_module("app.main").app
    path = tmp_path / "health.db"
    init_db(path)
    app.dependency_overrides[database_path] = lambda: path
    try:
        yield
    finally:
        app.dependency_overrides.pop(database_path, None)


def test_health_returns_ok():
    app = importlib.import_module("app.main").app
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("method", "path", "status_code"),
    [("GET", "/not-found", 404), ("POST", "/health", 405)],
)
def test_http_errors_return_chinese_json(method, path, status_code):
    app = importlib.import_module("app.main").app
    with TestClient(app) as client:
        response = client.request(method, path)

    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    assert any("\u4e00" <= character <= "\u9fff" for character in response.json()["detail"])
    if status_code == 405:
        assert "GET" in response.headers["allow"]


def test_unexpected_error_hides_internal_details(monkeypatch):
    app = importlib.import_module("app.main").app
    monkeypatch.setattr(app.router, "routes", list(app.router.routes))

    def fail():
        raise RuntimeError("private-internal-detail")

    app.add_api_route("/_test/failure", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_test/failure")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert any("\u4e00" <= character <= "\u9fff" for character in response.json()["detail"])
    assert "private-internal-detail" not in response.text
    assert "Traceback" not in response.text
