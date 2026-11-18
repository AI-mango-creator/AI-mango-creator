import json
from contextlib import closing
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.db import connect_db
from app.llm import client
from app.main import app
from app.routers import outfits
from app.routers.wardrobe import database_path
from app.services.fallback import fallback_outfits
from app.services.filter import filter_candidates
from scripts.claim_legacy import claim_legacy
from scripts.seed import seed_database

DATA = json.loads((Path(__file__).resolve().parents[2] / "cases/cases.json").read_text())
OWNER = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def api(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    seed_database(path)
    claim_legacy(path, device_id=OWNER, apply=True)
    app.dependency_overrides[database_path] = lambda: path
    monkeypatch.setattr(client, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-secret")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("DASHSCOPE_MODEL", "test-model")
    try:
        with TestClient(app, headers={"X-Device-ID": OWNER}) as http:
            yield http, path
    finally:
        app.dependency_overrides.pop(database_path, None)


def transport(monkeypatch, handler):
    real = httpx2.Client
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(
        transport=httpx2.MockTransport(handler), **kwargs,
    ))


def legal_response(path, **scenario):
    filtered = filter_candidates(outfits.list_items(path, OWNER), **scenario)
    result = fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
    return httpx2.Response(200, json={"choices": [{"message": {
        "content": json.dumps({"sets": [item.model_dump() for item in result.sets]}, ensure_ascii=False),
    }}]})


def test_saved_profile_used_only_by_owner_and_version_persisted(api, monkeypatch):
    http, path = api
    http.patch('/api/profile', json={'height_cm': 168.5, 'body_shape': 'TY'})
    other = '22222222-2222-4222-8222-222222222222'
    http.patch('/api/profile', headers={'X-Device-ID': other}, json={'height_cm': 190})
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(json.loads(body['messages'][1]['content']))
        return legal_response(path, temp_c=18, occasion='commute')

    transport(monkeypatch, handler)
    result = http.post('/api/outfits', json={'temp_c': 18, 'occasion': 'commute'})
    assert result.status_code == 200
    assert sent[0]['body_profile'] == {'height_cm': 168.5, 'body_shape': 'TY'}
    assert result.json()['prompt_version'] == 'outfit_compose.v2'
    with closing(connect_db(path)) as db:
        assert db.execute('SELECT prompt_version FROM sessions WHERE id=?', (result.json()['session_id'],)).fetchone()[0] == 'outfit_compose.v2'


def test_real_pipeline_persists_session_sets_items_and_sources(api, monkeypatch):
    http, path = api
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return legal_response(path, temp_c=18, occasion="commute")

    transport(monkeypatch, handler)
    response = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["sets"]) == 3
    assert body["degraded"] is False
    assert body["degrade_reason"] is None
    assert body["prompt_version"] == "outfit_compose.v1"
    assert body["latency_ms"] >= 0
    assert len(calls) == 1
    with closing(connect_db(path)) as connection:
        session = connection.execute("SELECT * FROM sessions WHERE id=?", (body["session_id"],)).fetchone()
        assert session["latency_ms"] == body["latency_ms"]
        assert session["status"] == "ok"
        assert connection.execute("SELECT count(*) FROM outfit_sets").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM outfit_items").fetchone()[0] == 12
        for row in connection.execute("SELECT sources FROM outfit_items"):
            assert json.loads(row["sources"])["item_id"] == "model"
    for outfit in body["sets"]:
        assert set(outfit["slots"].values()) - {None} == {item["id"] for item in outfit["items"]}


@pytest.mark.parametrize("case_id", ["C01", "C02"])
def test_shortage_is_200_without_model_call(api, monkeypatch, case_id):
    http, path = api
    case = next(case for case in DATA["cases"] if case["id"] == case_id)
    inputs = case["input"]
    ids = inputs.get("wardrobe_override", ["W04", "W06", "W09"])
    with closing(connect_db(path)) as connection, connection:
        connection.execute("DELETE FROM wardrobe_items WHERE id NOT IN (?,?,?)", ids)

    def forbidden(*args, **kwargs):
        pytest.fail("候选不足不得调用模型")

    monkeypatch.setattr(client, "chat", forbidden)
    response = http.post("/api/outfits", json={key: value for key, value in inputs.items() if key != "wardrobe_override"})
    assert response.status_code == 200
    body = response.json()
    assert body["sets"] == []
    assert body["shortage"]["top"]["slot"] == "top"
    assert body["shortage_hint"]
    assert body["degraded"] is False
    with closing(connect_db(path)) as connection:
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM outfit_sets").fetchone()[0] == 0


@pytest.mark.parametrize("body", [
    {}, {"temp_c": "18", "occasion": "commute"}, {"temp_c": 18, "occasion": "invalid"},
    {"temp_c": 18, "occasion": "commute", "formality_target": [5, 1]},
    {"temp_c": 18, "occasion": "commute", "formality_target": [0, 6]},
    {"temp_c": 18, "occasion": "commute", "wardrobe_override": ["W01"]},
])
def test_invalid_request_is_400_and_no_session(api, body):
    http, path = api
    response = http.post("/api/outfits", json=body)
    assert response.status_code == 400
    assert "参数" in response.json()["detail"]
    with closing(connect_db(path)) as connection:
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_timeout_fallback_persists_derived_sources(api, monkeypatch):
    http, path = api

    def handler(request):
        raise httpx2.ReadTimeout("private-internal")

    transport(monkeypatch, handler)
    body = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"}).json()
    assert body["degraded"] is True
    assert body["degrade_reason"] == "timeout"
    with closing(connect_db(path)) as connection:
        session = connection.execute("SELECT * FROM sessions").fetchone()
        assert session["status"] == "degraded"
        assert session["fallback_type"] == "timeout"
        assert all(json.loads(row[0])["reason"] == "derived" for row in connection.execute("SELECT sources FROM outfit_sets"))
        assert all(json.loads(row[0])["item_id"] == "derived" for row in connection.execute("SELECT sources FROM outfit_items"))


def test_latency_counts_read_model_and_persistence(api, monkeypatch):
    http, path = api
    clock = [0.0]
    original_read, original_generate, original_save = outfits.list_items, outfits.generate_outfits, outfits._persist
    monkeypatch.setattr(outfits, "perf_counter", lambda: clock[0])

    def read(*args, **kwargs):
        clock[0] += 0.1
        return original_read(*args, **kwargs)

    def generate(*args, **kwargs):
        clock[0] += 0.2
        return original_generate(*args, **kwargs)

    def save(*args, **kwargs):
        clock[0] += 0.05
        return original_save(*args, **kwargs)

    monkeypatch.setattr(outfits, "list_items", read)
    monkeypatch.setattr(outfits, "generate_outfits", generate)
    monkeypatch.setattr(outfits, "_persist", save)
    transport(monkeypatch, lambda request: legal_response(path, temp_c=18, occasion="commute"))
    body = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"}).json()
    # 测试响应生成也读了一次衣柜，累计 100+200+100+50ms。
    assert body["latency_ms"] == 450


def test_explicit_formality_and_excluded_reach_model_and_session(api, monkeypatch):
    http, path = api
    scenario = {"temp_c": 22, "occasion": "date", "formality_target": [1, 3], "excluded": ["W04"]}
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return legal_response(path, **scenario)

    transport(monkeypatch, handler)
    response = http.post("/api/outfits", json=scenario)
    assert response.status_code == 200
    assert all(item["id"] != "W04" for outfit in response.json()["sets"] for item in outfit["items"])
    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["formality_target"] == [1, 3]
    assert "W04" not in {item["id"] for item in payload["candidates"]}
    with closing(connect_db(path)) as connection:
        row = connection.execute("SELECT * FROM sessions").fetchone()
        assert json.loads(row["excluded_items"]) == ["W04"]
        assert json.loads(row["formality_target"]) == [1, 3]
        assert json.loads(row["sources"])["formality_target"] == "user"


def test_auth_degrade_reason_not_mislabeled_as_timeout(api, monkeypatch):
    http, path = api
    transport(monkeypatch, lambda request: httpx2.Response(403))
    response = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"})
    assert response.status_code == 200
    assert response.json()["degrade_reason"] == "auth"
    assert response.json()["degraded"] is True
    with closing(connect_db(path)) as connection:
        row = connection.execute("SELECT * FROM sessions").fetchone()
        assert row["status"] == "degraded"
        assert row["fallback_type"] is None


def test_unrecoverable_network_error_records_failed_session(api, monkeypatch):
    http, path = api
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx2.ConnectError("private-internal")

    transport(monkeypatch, handler)
    response = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"})
    assert response.status_code == 500
    assert "private-internal" not in response.text
    assert len(calls) == 3
    with closing(connect_db(path)) as connection:
        row = connection.execute("SELECT * FROM sessions").fetchone()
        assert row["status"] == "failed"
        assert row["latency_ms"] >= 0
        assert connection.execute("SELECT count(*) FROM outfit_sets").fetchone()[0] == 0


def test_server_latency_includes_rate_limit_wait_without_sleeping(api, monkeypatch):
    http, path = api
    clock, calls, waits = [0.0], [], []
    original_generate = outfits.generate_outfits
    monkeypatch.setattr(outfits, "perf_counter", lambda: clock[0])

    def wait(seconds):
        waits.append(seconds)
        clock[0] += seconds

    def generate(*args, **kwargs):
        return original_generate(*args, **kwargs, wait=wait)

    def limited(request):
        calls.append(request)
        return httpx2.Response(429)

    monkeypatch.setattr(outfits, "generate_outfits", generate)
    transport(monkeypatch, limited)
    response = http.post("/api/outfits", json={"temp_c": 18, "occasion": "commute"})
    assert response.status_code == 200
    assert response.json()["latency_ms"] == 5000
    assert response.json()["degrade_reason"] == "rate_limit"
    assert len(calls) == 2
    assert waits == [5]
    with closing(connect_db(path)) as connection:
        assert connection.execute("SELECT latency_ms FROM sessions").fetchone()[0] == 5000
