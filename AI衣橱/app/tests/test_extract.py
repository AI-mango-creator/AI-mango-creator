import asyncio
import csv
import json
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from app.models import WardrobeItem
from app.services.extract import apply_category_rules, extract_record, strip_fences
from scripts.batch_extract import run_batch, select_ready_cases, write_report

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs/reports/raw/recognition"


@pytest.mark.parametrize(('kind', 'group'), [('set', 'sets'), ('bag', 'bags'), ('jewelry', 'jewelry'), ('unknown', 'unclassified')])
def test_v3_new_categories_are_stored_but_not_used_as_outfits(item, kind, group):
    from app.services.extract import parse_items_v3
    from app.services.filter import filter_candidates
    result = parse_items_v3(json.dumps({'items': [item | {'category': kind}]}), image_path='uploads/photo.jpg')
    assert result[0].wardrobe_group == group
    assert result[0].category is None
    assert result[0].needs_confirm
    assert result[0].sources['wardrobe_group'] == 'model'
    assert not filter_candidates([result[0].confirm_recognition()], temp_c=18, occasion='commute')['candidates']


def test_v3_schema_is_single_source_and_fences_still_parse(item):
    from app.models import ExtractionResponse
    from app.services.extract import parse_items_v3
    template = (ROOT / 'prompts/item_extract.v3.md').read_text()
    assert template.count('{{JSON_SCHEMA}}') == 1
    assert '"items"' not in template
    assert 'bag' in json.dumps(ExtractionResponse.model_json_schema())
    result = parse_items_v3('```json\n' + json.dumps({'items': [item]}) + '\n```', image_path='x')
    assert result[0].category == item['category']


def record(case_id):
    return json.loads((RAW / f"{case_id}.json").read_text())


@pytest.fixture
def item():
    return record("R01")["parsed"]["items"][0]


@pytest.mark.parametrize("variant", ["bare", "json", "no_language"])
def test_three_fence_variants(variant):
    source = record("R02" if variant == "bare" else "R01")
    raw = source["raw_content"]
    if variant == "no_language":
        # 仅去掉真实围栏的语言标记，JSON 原文逐字保留。
        raw = raw.replace("```json", "```", 1)
    assert json.loads(strip_fences(raw)) == source["parsed"]


def test_outer_correction_is_explicit_and_keeps_confidence(item):
    # 从真实 R01 派生故障注入，不计入原始录制的指标。
    before = WardrobeItem(id="V1", **(item | {"warmth": 1}))
    after, corrections = apply_category_rules(before)
    assert after.warmth == 2
    assert after.confidence == item["confidence"]
    assert after.sources["warmth"] == "derived"
    assert after.sources["confidence"] == "model"
    assert corrections and "1 -> 2" in corrections[0]
    assert before.warmth == 1


def test_seasons_narrowed_from_existing_filter_spec(item):
    before = WardrobeItem(id="V1", **(item | {"category": "top", "warmth": 5, "seasons": ["summer", "winter"]}))
    after, corrections = apply_category_rules(before)
    assert after.seasons == ["winter"]
    assert after.sources["seasons"] == "derived"
    assert any("seasons" in message and "summer" in message for message in corrections)


def test_shoes_keep_d9_season_semantics(item):
    before = WardrobeItem(id="V1", **(item | {"category": "shoes", "warmth": 5, "seasons": ["summer"]}))
    after, corrections = apply_category_rules(before)
    assert after.seasons == ["summer"]
    assert corrections == []


def test_non_clothing_is_not_forced_into_a_category():
    source = record("R01") | {"raw_content": '{"items":[]}', "had_fence": False,
                               "parsed": {"items": []}, "checks": {"item_count": False}}
    result = extract_record(source)
    assert result["actual"] == {"category": None, "reason": "NOT_CLOTHING"}
    assert result["status_code"] == 422


def test_batch_concurrency_three_and_stable_order(tmp_path):
    cases = select_ready_cases(json.loads((ROOT / "cases/cases.json").read_text()))
    active, peak = 0, 0

    async def process(source):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.001 * (10 - int(source["case_id"][1:])))
            return extract_record(source)
        finally:
            active -= 1

    rows = asyncio.run(run_batch(cases, process=process))
    assert peak == 3
    assert [row["case_id"] for row in rows] == [case["id"] for case in cases]
    destination = tmp_path / "eval.csv"
    write_report(destination, rows)
    with destination.open(encoding="utf-8-sig") as handle:
        written = list(csv.DictReader(handle))
    assert "sub" in json.loads(written[2]["corrections"])[0]
    assert written[0]["是否含围栏"] == "true"
    assert int(written[0]["耗时"]) == record("R01")["latency_ms"]


def test_ready_selector_only_r01_to_r09():
    cases = [{"id": name, "input": {"image_status": status}} for name, status in (
        ("R01", "ready"), ("R02", "pending"), ("A01", "ready"), ("R10", "ready"))]
    assert [case["id"] for case in select_ready_cases({"cases": cases})] == ["R01"]


def test_r03_failure_is_not_repaired_or_regraded():
    source = record("R03")
    result = extract_record(source)
    assert result["actual"]["sub"] == "长裤"
    assert result["checks"] == source["checks"]
    assert result["checks"]["sub_in"] is False
    assert any("sub" in message for message in result["corrections"])


@pytest.mark.parametrize("case_id", [f"R{index:02}" for index in range(1, 10)])
def test_nine_recorded_responses_parse_and_keep_metadata(case_id):
    source = record(case_id)
    result = extract_record(source)
    assert result["raw_actual"] == source["parsed"]["items"][0]
    assert result["latency_ms"] == source["latency_ms"]
    assert result["had_fences"] == source["had_fence"]
    assert result["checks"] == source["checks"]


def test_prompt_hash_mismatch_is_rejected():
    with pytest.raises(ValueError, match="prompt"):
        extract_record(record("R01") | {"prompt_sha256_prefix": "0000000000000000"})


def test_v2_prompt_only_adds_one_specific_sub_constraint():
    original = (ROOT / "prompts/item_extract.v1.md").read_text()
    updated = (ROOT / "prompts/item_extract.v2.md").read_text()
    assert updated == original + "sub 必须给具体款型名，禁止使用「长裤 / 裤子 / 上衣 / 外套 / 鞋子」等上位词。\n"


def test_record_selects_v2_prompt_and_still_checks_its_hash():
    prompt = ROOT / "prompts/item_extract.v2.md"
    source = record("R01") | {"prompt_file": "prompts/item_extract.v2.md",
                               "prompt_sha256_prefix": sha256(prompt.read_bytes()).hexdigest()[:16]}
    assert extract_record(source)["checks"] == source["checks"]
    with pytest.raises(ValueError, match="prompt"):
        extract_record(source | {"prompt_sha256_prefix": record("R01")["prompt_sha256_prefix"]})


@pytest.mark.parametrize("path", [".env", "../.env", str(ROOT / ".env"),
                                    "prompts/../.env", "prompts/item_extract.v3.md"])
def test_record_prompt_path_whitelist_rejects_other_paths(path):
    with pytest.raises(ValueError, match="prompt"):
        extract_record(record("R01") | {"prompt_file": path})


def test_prompt_whitelist_rejects_symlink_escape(tmp_path, monkeypatch):
    from app.services import extract

    (tmp_path / "prompts").mkdir()
    target = tmp_path / "private.txt"
    target.write_text("must not read")
    (tmp_path / "prompts/item_extract.v2.md").symlink_to(target)
    monkeypatch.setattr(extract, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="prompt"):
        extract.resolve_prompt_file("prompts/item_extract.v2.md")


def test_vision_rate_limit_wait_is_injectable(tmp_path, monkeypatch):
    import httpx2

    from app.llm import client
    from app.services.extract import parse_items

    calls, waits = [], []
    def transport(request):
        calls.append(json.loads(request.content))
        return httpx2.Response(429, json={"error": {"message": "You have exceeded your current request limit.",
                                                     "type": "limit_requests", "param": None, "code": "limit_requests"}})

    real = httpx2.Client
    monkeypatch.setattr(client, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "text-model"))
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(transport), **kwargs))
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    result = client.vision("test", ROOT / "cases/images/cloth01.jpg", model="vision-model", prompt_version="item_extract.v2",
                           case_id="R01", wait=waits.append, validate=lambda raw: parse_items(raw, image_path="x"))
    assert len(calls) == 2 and waits == [5]
    assert result["category"] == "rate_limit"
    assert "429" in calls[1]["messages"][-1]["content"]


def test_vision_client_validates_and_retries_with_feedback(tmp_path, monkeypatch):
    import httpx2

    from app.llm import client
    from app.services.extract import parse_items

    seen = []
    def transport(request):
        seen.append(json.loads(request.content))
        content = "not JSON" if len(seen) == 1 else record("R02")["raw_content"]
        return httpx2.Response(200, json={"choices": [{"message": {"content": content}}]})

    real = httpx2.Client
    monkeypatch.setattr(client, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "text-model"))
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(transport), **kwargs))
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    result = client.vision("test prompt", ROOT / "cases/images/cloth02.jpg", model="vision-model",
                           prompt_version="item_extract.v2", case_id="R02", validate=lambda raw: parse_items(raw, image_path="x"))
    assert len(seen) == 2
    assert seen[0]["temperature"] == 0
    assert seen[0]["model"] == "vision-model"
    assert seen[1]["messages"][-1]["role"] == "user"
    assert "校验" in seen[1]["messages"][-1]["content"]
    assert result["raw_content"] == record("R02")["raw_content"]
    assert len(result["attempts"]) == 2
    log = (tmp_path / "llm.log").read_text()
    assert "test-secret" not in log and "base64" not in log


@pytest.mark.parametrize("failure,expected_calls", [("timeout", 1), ("auth", 1), ("parse", 3)])
def test_vision_failure_budget(tmp_path, monkeypatch, failure, expected_calls):
    import httpx2

    from app.llm import client
    from app.services.extract import parse_items

    calls = []
    def transport(request):
        calls.append(True)
        if failure == "timeout":
            raise httpx2.ReadTimeout("timeout", request=request)
        if failure == "auth":
            return httpx2.Response(401, json={"error": {"message": "unauthorized"}})
        return httpx2.Response(200, json={"choices": [{"message": {"content": "not JSON"}}]})

    real = httpx2.Client
    monkeypatch.setattr(client, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "text-model"))
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(transport), **kwargs))
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    result = client.vision("test", ROOT / "cases/images/cloth01.jpg", model="vision-model",
                           prompt_version="item_extract.v2", case_id="R01", validate=lambda raw: parse_items(raw, image_path="x"))
    assert len(calls) == expected_calls
    assert result["error"]
    assert len(result["attempts"]) == expected_calls


def test_v2_recorder_concurrency_provenance_and_no_overwrite(tmp_path):
    import threading
    import time

    from scripts.record_recognition import record_cases

    data = json.loads((ROOT / "cases/cases.json").read_text())
    active = peak = 0
    lock = threading.Lock()
    def injected(prompt, image, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.005)
            index = int(image.stem[-2:])
            raw = record(f"R{index:02}")
            kwargs["validate"](raw["raw_content"])
            return {"http_status": 200, "raw_content": raw["raw_content"], "latency_ms": raw["latency_ms"],
                    "error": None, "attempts": [{"http_status": 200, "raw_content": raw["raw_content"]}]}
        finally:
            with lock:
                active -= 1

    summary = record_cases(data, out_dir=tmp_path, vision=injected)
    assert peak == 3
    assert [entry["case_id"] for entry in summary["records"]] == [f"R{i:02}" for i in range(1, 10)]
    assert (tmp_path / "summary_v2.json").is_file()
    assert json.loads((tmp_path / "R03.json").read_text())["checks"]["sub_in"] is False
    assert summary["prompt_file"] == "prompts/item_extract.v2.md"
    with pytest.raises(ValueError, match="已存在"):
        record_cases(data, out_dir=tmp_path, vision=injected)


@pytest.mark.parametrize("with_content", [False, True])
def test_v2_protocol_failures_stay_in_denominator(tmp_path, monkeypatch, with_content):
    from app.services import extract
    from scripts.evaluate import evaluate
    from scripts.record_recognition import record_cases

    data = json.loads((ROOT / "cases/cases.json").read_text())
    def failed(*args, **kwargs):
        return {"http_status": 200, "raw_content": record("R01")["raw_content"] if with_content else None, "latency_ms": 10,
                "error": "模型服务响应格式无效", "attempts": []}

    directory = tmp_path / "recognition_v2"
    summary = record_cases(data, out_dir=directory, vision=failed)
    assert summary["case_pass"] == 0 and summary["cases"] == 9
    with pytest.raises(extract.ExtractError):
        extract.extract_record(json.loads((directory / "R01.json").read_text()))
    def unrelated_composition(case, *args, **kwargs):
        # 本测试只查识别失败的分母，组合部分由test_evaluate独立验证。
        return {"case_id": case["id"], "source": "真实调用", "attempts": [{"http_status": 200}],
                "passed": True, "latency_ms": 1, "degraded": False}

    monkeypatch.setattr("scripts.evaluate.run_compose_case", unrelated_composition)
    report = evaluate(data, raw_dir=tmp_path, model="test-model", recognition_dir=directory, version="v2")
    assert len(report["rows"]) == 24
    recognition = [row for row in report["rows"] if row["case_id"].startswith("R")]
    assert len(recognition) == 9 and all(not row["passed"] for row in recognition)


def test_recorder_does_not_override_client_failure_with_parseable_content(tmp_path):
    from scripts.record_recognition import record_cases

    def truncated(prompt, image, **kwargs):
        raw = record(f"R{int(image.stem[-2:]):02}")
        return {"http_status": 200, "raw_content": raw["raw_content"], "latency_ms": 10,
                "error": "响应未完整结束", "category": "parse", "attempts": []}

    data = json.loads((ROOT / "cases/cases.json").read_text())
    summary = record_cases(data, out_dir=tmp_path, vision=truncated)
    assert summary["case_pass"] == 0
    assert summary["parse_ok"] == 0


def test_sources_audit_namespaces_do_not_allow_relabeling_regular_fields():
    from pydantic import ValidationError

    data = record("R01")["parsed"]["items"][0] | {"id": "upload-test"}
    good = {"source": "derived", "entries": ["warmth校正"]}
    item = WardrobeItem.model_validate(data | {"sources": {"_corrections": good}})
    assert item.model_dump(mode="json")["sources"]["_corrections"] == good
    assert item.sources["confidence"] == "model"
    for sources in ({"confidence": good}, {"_unknown": good}, {"_corrections": {"source": "user", "entries": []}}):
        with pytest.raises(ValidationError):
            WardrobeItem.model_validate(data | {"sources": sources})


def test_vision_uses_png_mime_without_modifying_prompt_or_model(tmp_path, monkeypatch):
    import httpx2

    from app.llm import client
    from app.services.extract import parse_items

    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json={"choices": [{"message": {"content": record("R02")["raw_content"]}}]})

    real = httpx2.Client
    monkeypatch.setattr(client, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "text-model"))
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(transport), **kwargs))
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    image = tmp_path / "photo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    client.vision("unchanged", image, mime_type="image/png", model="qwen3.8-omni-flash", prompt_version="item_extract.v2",
                  case_id="upload:test", validate=lambda raw: parse_items(raw, image_path="uploads/photo.png"))
    assert requests[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert requests[0]["messages"][0]["content"][0]["text"] == "unchanged"


def test_cli_bad_record_has_chinese_error_without_traceback(tmp_path):
    copied = tmp_path / "records"
    shutil.copytree(RAW, copied)
    invalid = record("R01") | {"raw_content": "not json", "had_fence": False}
    (copied / "R01.json").write_text(json.dumps(invalid))
    output = tmp_path / "report.csv"
    result = subprocess.run([sys.executable, "-m", "scripts.batch_extract", "--records", str(copied),
                             "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "离线跑批失败" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_cli_replays_canonical_metrics_and_keeps_real_failure(tmp_path):
    output = tmp_path / "report.csv"
    result = subprocess.run([sys.executable, "-m", "scripts.batch_extract", "--output", str(output)],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 1  # 保留 R03 原始失败，不将它伪装成全绿。
    assert "用例通过 8/9" in result.stdout
    assert "单张平均 16258ms" in result.stdout
    with output.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 9
    assert json.loads(rows[2]["逐字段一致"])["sub_in"] is False
    corrected = json.loads(rows[6]["实际"])
    assert corrected["raw"]["seasons"] == ["summer", "spring"]
    assert corrected["corrected"]["seasons"] == ["summer"]
    assert corrected["sources"][0]["seasons"] == "derived"
    assert json.loads(rows[6]["corrections"])


@pytest.mark.parametrize("confidence", [0.1, 0.59, 0.6, 0.95, 0.99, 1.0])
def test_all_recognized_uploads_need_confirmation_regardless_of_confidence(confidence):
    from app.services.extract import parse_items
    record = json.loads((ROOT / "docs/reports/raw/recognition/R01.json").read_text())
    payload = record["parsed"]
    payload["items"][0]["confidence"] = confidence
    item = parse_items(json.dumps(payload), image_path="uploads/device/photo.jpg")[0]
    assert item.needs_confirm is True
    assert item.confidence == confidence and item.sources["confidence"] == "model"
