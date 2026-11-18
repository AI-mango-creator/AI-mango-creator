import copy
import json
import re
from itertools import product
from pathlib import Path

import httpx2
import pytest

from app.llm import client
from app.models import Composition, WardrobeItem
from app.services.compose import ComposeError, compose_outfits
from app.services.filter import filter_candidates

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "cases/cases.json").read_text())


class ScriptedChat:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append((copy.deepcopy(messages), kwargs))
        return next(self.responses)


@pytest.fixture
def scenario():
    return {"temp_c": 18, "occasion": "commute", "formality_target": [3, 5]}


@pytest.fixture
def filtered(scenario):
    wardrobe = [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]
    return filter_candidates(wardrobe, **scenario)


@pytest.fixture
def payload(filtered):
    groups = {slot: [item for item in filtered["candidates"] if item.category == slot]
              for slot in ("top", "bottom", "outer", "shoes")}
    sets = []
    for selection in product(*groups.values()):
        sets.append({"slots": dict(zip(groups, (item.id for item in selection))) | {"dress": None},
                     "reason": f"采用{selection[0].colors[0]}上装。"})
        if len(sets) == 3:
            break
    return {"sets": sets}


def test_parse_failure_feedback_then_parse_error(filtered, scenario):
    chat = ScriptedChat("不是 JSON", "仍不是 JSON")
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario, chat=chat)
    assert error.value.detail.attribution == "PARSE"
    assert len(chat.calls) == 2
    messages = chat.calls[1][0]
    assert messages[-1]["role"] == "user"
    assert "PARSE" in messages[-1]["content"]
    assert "json_invalid" in messages[-1]["content"]


def test_two_tops_regenerate_once(filtered, scenario, payload):
    bad = copy.deepcopy(payload)
    tops = [item.id for item in filtered["candidates"] if item.category == "top"]
    bad["sets"][0]["slots"]["bottom"] = tops[1]
    chat = ScriptedChat(json.dumps(bad), json.dumps(payload))
    result = compose_outfits(filtered, **scenario, chat=chat)
    assert len(result.sets) == 3
    assert result.degraded is False
    assert len(chat.calls) == 2
    assert "槽位" in chat.calls[1][0][-1]["content"]
    assert chat.calls[1][0][-2]["role"] == "assistant"


def test_validation_still_fails_is_compose_error(filtered, scenario, payload):
    payload["sets"][0]["reason"] = "显瘦"
    chat = ScriptedChat(json.dumps(payload), json.dumps(payload))
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario, chat=chat)
    assert error.value.detail.attribution == "COMPOSE"
    assert len(chat.calls) == 2


@pytest.mark.parametrize("case_id", ["C01", "C02"])
def test_shortage_never_calls_model(case_id):
    case = next(case for case in DATA["cases"] if case["id"] == case_id)
    wardrobe = [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]
    inputs = case["input"]
    keys = {"temp_c", "occasion", "excluded", "formality_target", "wardrobe_override"}
    filtered = filter_candidates(wardrobe, **{key: val for key, val in inputs.items() if key in keys})
    chat = ScriptedChat()
    result = compose_outfits(filtered, temp_c=inputs["temp_c"], occasion=inputs["occasion"], chat=chat)
    assert result.sets == []
    assert result.shortage.model_dump() == filtered["shortage"]
    assert result.shortage_hint
    assert len(chat.calls) == 0


def test_prompt_schema_single_source(filtered, scenario, payload):
    template = (ROOT / "prompts/outfit_compose.v1.md").read_text()
    assert template.count("{{JSON_SCHEMA}}") == 1
    assert not re.search(r"\b(sets|slots|top|bottom|outer|shoes|dress|reason)\b", template)
    chat = ScriptedChat(json.dumps(payload))
    compose_outfits(filtered, **scenario, chat=chat)
    messages, kwargs = chat.calls[0]
    assert "{{JSON_SCHEMA}}" not in messages[0]["content"]
    assert json.dumps(Composition.model_json_schema(), ensure_ascii=False) in messages[0]["content"]
    assert kwargs == {"schema": Composition, "timeout": 20, "max_retries": 2}


def test_body_profile_only_enters_compose_payload(filtered, scenario, payload):
    ids = [item.id for item in filtered['candidates']]
    chat = ScriptedChat(json.dumps(payload))
    result = compose_outfits(filtered, **scenario, chat=chat,
                             profile={'height_cm': 165.5, 'weight_kg': 55, 'body_shape': 'A'})
    sent = json.loads(chat.calls[0][0][1]['content'])
    assert sent['body_profile'] == {'height_cm': 165.5, 'weight_kg': 55, 'body_shape': 'A'}
    assert [x['id'] for x in sent['candidates']] == ids
    assert result.prompt_version == 'outfit_compose.v2'
    assert '不用于' in chat.calls[0][0][0]['content']


def test_profile_fallback_preserves_version(filtered, scenario):
    from app.services.compose import generate_outfits
    chat = ScriptedChat('not json', 'not json')
    result = generate_outfits(filtered, **scenario, chat=chat, profile={'height_cm': 170})
    assert result.degraded
    assert result.prompt_version == 'outfit_compose.v2'


@pytest.fixture
def client_config(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    for name in ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    client.ENV_PATH.write_text(
        "DASHSCOPE_API_KEY=test-secret\nDASHSCOPE_BASE_URL=https://example.invalid/v1\n"
        "DASHSCOPE_MODEL=test-model\n"
    )


def install_transport(monkeypatch, handler):
    real_client = httpx2.Client
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real_client(
        transport=httpx2.MockTransport(handler), **kwargs,
    ))


def envelope(payload):
    return {"choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 34}}


def test_real_default_path_wire_and_safe_log(monkeypatch, client_config, filtered, scenario, payload):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, json=envelope(payload))

    install_transport(monkeypatch, handler)
    result = compose_outfits(filtered, **scenario, case_id="B01")
    assert len(result.sets) == 3
    body = json.loads(requests[0].content)
    assert str(requests[0].url) == "https://example.invalid/v1/chat/completions"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] > 0
    assert body["response_format"]["json_schema"]["schema"] == Composition.model_json_schema()
    assert body["response_format"]["json_schema"]["strict"] is True
    assert max(requests[0].extensions["timeout"].values()) <= 20
    log = client.LOG_PATH.read_text()
    assert "test-secret" not in log
    entry = json.loads(log)
    assert entry["case_id"] == "B01"
    assert entry["prompt_version"] == "outfit_compose.v1"
    assert entry["latency_ms"] >= 0
    assert entry["prompt_tokens"] == 12
    assert entry["completion_tokens"] == 34
    assert entry["degraded"] is False


def test_missing_key_readable_at_call_only(monkeypatch, client_config):
    client.ENV_PATH.write_text("")
    with pytest.raises(client.LLMError, match="DASHSCOPE_API_KEY"):
        client.chat([], schema=Composition)


def test_timeout_no_retry(monkeypatch, client_config, filtered, scenario):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx2.ReadTimeout("test-secret must not leak", request=request)

    install_transport(monkeypatch, handler)
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario)
    assert error.value.detail.code == "MODEL_TIMEOUT"
    assert len(calls) == 1
    assert "test-secret" not in str(error.value)
    assert "test-secret" not in client.LOG_PATH.read_text()


def test_network_and_regeneration_share_three_attempt_budget(
    monkeypatch, client_config, filtered, scenario,
):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx2.Response(503)
        return httpx2.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    install_transport(monkeypatch, handler)
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario)
    assert error.value.detail.attribution == "PARSE"
    assert len(calls) == 3
    assert calls[1]["messages"][-1]["role"] == "user"
    assert "503" in calls[1]["messages"][-1]["content"]
    assert "PARSE" in calls[2]["messages"][-1]["content"]
    assert len(client.LOG_PATH.read_text().splitlines()) == 3


def test_budget_exhausted_after_parse_keeps_parse_attribution(
    monkeypatch, client_config, filtered, scenario,
):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) <= 2:
            return httpx2.Response(503)
        return httpx2.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    install_transport(monkeypatch, handler)
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario)
    assert error.value.detail.attribution == "PARSE"
    assert len(calls) == 3


def test_partial_candidate_count_is_honest(filtered, scenario, payload):
    selected = {value for value in payload["sets"][0]["slots"].values() if value}
    narrowed = dict(filtered, candidates=[item for item in filtered["candidates"] if item.id in selected])
    payload["sets"] = payload["sets"][:1]
    chat = ScriptedChat(json.dumps(payload))
    result = compose_outfits(narrowed, **scenario, chat=chat)
    assert len(result.sets) == 1
    assert result.shortage_hint
    assert json.loads(chat.calls[0][0][1]["content"])["target_set_count"] == 1


def test_http_auth_failure_does_not_leak_body(monkeypatch, client_config, filtered, scenario):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(401, text="test-secret")

    install_transport(monkeypatch, handler)
    with pytest.raises(ComposeError) as error:
        compose_outfits(filtered, **scenario)
    assert "401" in str(error.value)
    assert "test-secret" not in str(error.value)
    assert "test-secret" not in client.LOG_PATH.read_text()
    assert len(calls) == 1


def test_provider_envelope_parse_failure_regenerates(
    monkeypatch, client_config, filtered, scenario, payload,
):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx2.Response(200, text="not json")
        return httpx2.Response(200, json=envelope(payload))

    install_transport(monkeypatch, handler)
    assert len(compose_outfits(filtered, **scenario).sets) == 3
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "user"
    assert "PARSE" in calls[1]["messages"][-1]["content"]


def test_default_formality_target_reads_source(filtered, payload):
    chat = ScriptedChat(json.dumps(payload))
    compose_outfits(filtered, temp_c=18, occasion="commute", chat=chat)
    inputs = json.loads(chat.calls[0][0][1]["content"])
    assert inputs["formality_target"] == DATA["meta"]["filter_spec"]["occasion_formality"]["commute"]


def test_latency_includes_both_generations(monkeypatch, filtered, scenario, payload):
    from app.services import compose

    elapsed = [0.0]
    monkeypatch.setattr(compose, "perf_counter", lambda: elapsed[0])
    responses = iter(["not json", json.dumps(payload)])

    def chat(messages, **kwargs):
        elapsed[0] += 0.1
        return next(responses)

    result = compose_outfits(filtered, **scenario, chat=chat)
    assert result.latency_ms == 200
