import json
import re
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.llm import client
from app.llm.errors import ServiceError
from app.models import Composition, ErrorCategory, WardrobeItem
from app.services.compose import generate_outfits
from app.services.filter import filter_candidates

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = (ROOT / "docs/reports/api-error-samples.md").read_text(encoding="utf-8")
RATE_BODY, FORBIDDEN_BODY = re.findall(r"```json\n(.*?)\n```", SAMPLES, flags=re.DOTALL)
DATA = json.loads((ROOT / "cases/cases.json").read_text())


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    for name, value in {
        "DASHSCOPE_API_KEY": "test-secret", "DASHSCOPE_BASE_URL": "https://example.invalid/v1",
        "DASHSCOPE_MODEL": "test-model",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def filtered():
    return filter_candidates(
        [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]],
        temp_c=18, occasion="commute",
    )


def scripted_transport(monkeypatch, *responses):
    calls = []
    sequence = iter(responses)
    real_client = httpx2.Client

    def handler(request):
        calls.append(json.loads(request.content))
        response = next(sequence)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real_client(
        transport=httpx2.MockTransport(handler), **kwargs,
    ))
    return calls


def test_real_429_classified_and_wait_retried_once(monkeypatch, configured):
    calls = scripted_transport(monkeypatch, *[httpx2.Response(429, text=RATE_BODY) for _ in range(2)])
    waits = []
    with pytest.raises(client.LLMError) as error:
        client.chat([], schema=Composition, wait=waits.append)
    assert error.value.category == ErrorCategory.RATE_LIMIT
    assert waits == [5]
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "user"
    assert "429" in calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize(("status", "body", "diagnostic"), [
    (401, "", "invalid_key"), (403, FORBIDDEN_BODY, "model_unpurchased"),
])
def test_auth_no_retry_and_different_diagnostics(monkeypatch, configured, status, body, diagnostic):
    calls = scripted_transport(monkeypatch, httpx2.Response(status, text=body))
    waits = []
    with pytest.raises(client.LLMError) as error:
        client.chat([], schema=Composition, wait=waits.append)
    assert error.value.category == ErrorCategory.AUTH
    assert "AI 服务未授权，请检查配置" in str(error.value)
    assert waits == []
    assert len(calls) == 1
    entry = json.loads(client.LOG_PATH.read_text())
    assert entry["http_status"] == status
    assert entry["diagnostic"] == diagnostic
    if status == 403:
        assert entry["provider_code"] == "AccessDenied.Unpurchased"
    assert "test-secret" not in client.LOG_PATH.read_text()


def test_timeout_classified_no_retry(monkeypatch, configured):
    calls = scripted_transport(monkeypatch, httpx2.ReadTimeout("private-internal"))
    waits = []
    with pytest.raises(client.LLMError) as error:
        client.chat([], schema=Composition, wait=waits.append)
    assert error.value.category == ErrorCategory.TIMEOUT
    assert len(calls) == 1
    assert waits == []
    assert "private-internal" not in str(error.value)


def test_429_twice_generates_fallback_with_exact_two_calls(monkeypatch, configured, filtered):
    calls = scripted_transport(monkeypatch, *[httpx2.Response(429, text=RATE_BODY) for _ in range(2)])
    waits = []
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=waits.append, case_id="T8-429")
    assert result.degraded is True
    assert result.degrade_reason == "rate_limit"
    assert len(result.sets) == 3
    assert len(calls) == 2
    assert waits == [5]
    records = [json.loads(line) for line in client.LOG_PATH.read_text().splitlines()]
    assert sum(entry["event"] == "model_call" for entry in records) == 2
    assert records[-1]["event"] == "fallback"
    assert records[-1]["degraded"] is True
    assert all(entry["case_id"] == "T8-429" for entry in records)
    print("429 assertion: model_calls=2, retries=1, wait_requests=[5], degraded=true, degrade_reason=rate_limit")


def test_429_retry_success_does_not_degrade(monkeypatch, configured, filtered):
    from app.services.fallback import fallback_outfits

    valid = fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
    content = Composition(sets=valid.sets).model_dump_json()
    success = httpx2.Response(200, json={"choices": [{"message": {"content": content}}]})
    calls = scripted_transport(monkeypatch, httpx2.Response(429, text=RATE_BODY), success)
    waits = []
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=waits.append)
    assert result.degraded is False
    assert result.degrade_reason is None
    assert len(calls) == 2
    assert waits == [5]


@pytest.mark.parametrize(("response", "reason"), [
    (httpx2.Response(401), "auth"),
    (httpx2.Response(403, text=FORBIDDEN_BODY), "auth"),
    (httpx2.ReadTimeout("test-secret"), "timeout"),
])
def test_outer_entry_degrades_auth_and_timeout(monkeypatch, configured, filtered, response, reason):
    calls = scripted_transport(monkeypatch, response)
    waits = []
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=waits.append)
    assert result.degraded is True
    assert result.degrade_reason == reason
    assert len(result.sets) == 3
    assert len(calls) == 1
    assert waits == []


@pytest.mark.parametrize("raw", ["not json", '{"sets": [{"reason": "字段缺失"}]}'])
def test_parse_retry_then_fallback(monkeypatch, configured, filtered, raw):
    response = lambda: httpx2.Response(200, json={"choices": [{"message": {"content": raw}}]})
    calls = scripted_transport(monkeypatch, response(), response())
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=lambda seconds: None)
    assert result.degraded is True
    assert result.degrade_reason == "parse_failed"
    assert len(calls) == 2
    assert "PARSE" in calls[1]["messages"][-1]["content"]


def test_zero_delay_is_injectable(monkeypatch, configured):
    calls = scripted_transport(monkeypatch, *[httpx2.Response(429, text=RATE_BODY) for _ in range(2)])
    waits = []
    with pytest.raises(client.LLMError):
        client.chat([], schema=Composition, wait=waits.append, retry_delay=0)
    assert waits == [0]
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 422, 504, 500])
def test_safe_http_errors(status, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.router, "routes", list(app.router.routes))

    def fail():
        raise ServiceError(status)

    app.add_api_route("/_test/t8/error", fail)
    with TestClient(app, raise_server_exceptions=False) as http:
        response = http.get("/_test/t8/error")
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)
    assert any("\u4e00" <= char <= "\u9fff" for char in response.json()["detail"])
    assert "Traceback" not in response.text


def test_auth_http_message_is_user_safe(monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.router, "routes", list(app.router.routes))

    def fail():
        raise client.LLMError("MODEL_CONFIG", "test-secret", category=ErrorCategory.AUTH)

    app.add_api_route("/_test/t8/auth", fail)
    with TestClient(app, raise_server_exceptions=False) as http:
        response = http.get("/_test/t8/auth")
    assert response.status_code == 503
    assert response.json()["detail"] == "AI 服务暂不可用，请稍后再试"
    assert "test-secret" not in response.text


def test_rate_retry_is_shared_with_regeneration_budget(monkeypatch, configured, filtered):
    invalid = httpx2.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    calls = scripted_transport(monkeypatch, httpx2.Response(429, text=RATE_BODY), invalid,
                               httpx2.Response(429, text=RATE_BODY))
    waits = []
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=waits.append)
    assert len(calls) == 3
    assert waits == [5]
    assert result.degraded is True
    assert result.degrade_reason == "rate_limit"


def test_no_budget_left_means_no_rate_wait(monkeypatch, configured, filtered):
    calls = scripted_transport(monkeypatch, httpx2.Response(503), httpx2.Response(503),
                               httpx2.Response(429, text=RATE_BODY))
    waits = []
    result = generate_outfits(filtered, temp_c=18, occasion="commute", wait=waits.append)
    assert len(calls) == 3
    assert waits == []
    assert result.degrade_reason == "rate_limit"


def test_provider_error_code_cannot_leak_secret(monkeypatch, configured):
    # 在真实 403 结构中注入敏感值，字段名保持真实夹具原样。
    body = json.loads(FORBIDDEN_BODY)
    body["error"]["code"] = "test-secret"
    scripted_transport(monkeypatch, httpx2.Response(403, json=body))
    with pytest.raises(client.LLMError):
        client.chat([], schema=Composition)
    assert "test-secret" not in client.LOG_PATH.read_text()


def test_non_wardrobe_parameter_error_is_400(monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.router, "routes", list(app.router.routes))

    def parameters(quantity: int):
        return {"quantity": quantity}

    app.add_api_route("/_test/t8/parameters", parameters)
    with TestClient(app) as http:
        response = http.get("/_test/t8/parameters?quantity=bad")
    assert response.status_code == 400
    assert "参数" in response.json()["detail"]


def test_shortage_http_422_includes_structured_requirements(monkeypatch):
    from app.main import app
    from app.models import Shortage

    shortage = Shortage(missing_slots=["top"], requirements=[
        {"slot": "top", "warmth_min": 2, "formality_min": 4},
    ], message="缺少符合正式度要求的上装。")
    monkeypatch.setattr(app.router, "routes", list(app.router.routes))

    def fail():
        raise ServiceError(422, shortage=shortage)

    app.add_api_route("/_test/t8/shortage", fail)
    with TestClient(app) as http:
        response = http.get("/_test/t8/shortage")
    assert response.status_code == 422
    assert response.json()["shortage_hint"] == shortage.message
    assert response.json()["shortage"]["missing_slots"] == ["top"]
