import json
from copy import deepcopy
from pathlib import Path

import httpx2
import pytest

from app.llm import client
from app.models import Composition, WardrobeItem
from app.services.fallback import fallback_outfits
from app.services.filter import filter_candidates
from scripts.evaluate import (
    EvaluationInterrupted,
    assert_composition,
    evaluate,
    main,
    render_report,
    run_compose_case,
    split_cases,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "cases/cases.json").read_text())
WARDROBE = [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "test-model"))
    monkeypatch.setattr(client, "LOG_PATH", tmp_path / "llm.log")
    real = httpx2.Client

    def handler(request):
        messages = json.loads(request.content)["messages"]
        inputs = json.loads(messages[1]["content"])
        filtered = filter_candidates(WARDROBE, temp_c=inputs["temp_c"], occasion=inputs["occasion"],
                                     formality_target=inputs["formality_target"])
        candidates = [item for item in filtered["candidates"]
                      if item.id in {candidate["id"] for candidate in inputs["candidates"]}]
        legal = fallback_outfits(candidates, band=filtered["band"], degrade_reason="timeout")
        return httpx2.Response(200, json={"choices": [{"message": {
            "content": Composition(sets=legal.sets).model_dump_json(),
        }}]})

    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(
        transport=httpx2.MockTransport(handler), **kwargs,
    ))


def test_partition_is_24_plus_five_explicit_pending():
    runnable, skipped = split_cases(DATA)
    assert len(runnable) == 24
    assert [case["id"] for case in skipped] == [f"A{i:02}" for i in range(1, 6)]


def test_repeats_three_only_samples_b_and_preserves_each_evidence(tmp_path, monkeypatch, configured):
    import scripts.evaluate as runner
    from app.services import extract

    seen = []
    original = extract.extract_record
    def replay(record):
        seen.append(record["case_id"])
        return original(record)

    monkeypatch.setattr(extract, "extract_record", replay)
    monkeypatch.setattr(client, "vision", lambda *args, **kwargs: pytest.fail("R类不能重新调用视觉模型"))
    report = evaluate(DATA, raw_dir=tmp_path, model="test-model", version="v3", repeats=3,
                      recognition_dir=ROOT / "docs/reports/raw/recognition_v2")
    assert seen == [f"R{i:02}" for i in range(1, 10)]
    assert len(report["rows"]) == 24 and report["repeats"] == 3
    live = [row for row in report["rows"] if row["case_id"].startswith("B")]
    assert len(live) == 10
    assert sum(len(sample["attempts"]) for row in live for sample in row["samples"]) == 30
    for row in live:
        assert "passed" not in row
        assert row["sample_count"] == 3
        assert row["passed_count"] == sum(sample["passed"] for sample in row["samples"])
        assert len({sample["evidence"] for sample in row["samples"]}) == 3
        assert json.loads(Path(row["evidence"]).read_text()) == row
        for index, sample in enumerate(row["samples"], 1):
            assert sample["sample_index"] == index
            assert json.loads(Path(sample["evidence"]).read_text()) == sample
    rows = {row["case_id"]: row for row in report["rows"]}
    assert rows["B05"]["passed_count"] == rows["B10"]["passed_count"] == 0
    assert len(rows["C03"]["attempts"]) == len(rows["C05"]["attempts"]) == 2
    assert len(rows["C04"]["attempts"]) == 1
    assert rows["C01"]["attempts"] == rows["C02"]["attempts"] == []
    markdown = render_report(report)
    assert "R 类为单次录制，抖动区间见" in markdown
    assert "t11-repeatability.md" in markdown and "2/3" in markdown
    assert "n=30" in markdown
    assert "硬性通过数：" not in markdown and "平均" not in markdown
    assert sum(line.startswith("| [") for line in markdown.splitlines()) == 24
    assert "B01.json) | 3/3 |" in markdown
    # 聚合必须保留2/3的差别，不能按“任一次成功”折成布尔。
    mixed = deepcopy(live[0]["samples"])
    mixed[0].update(passed=False, failure_reasons=["注入解析失败"], attribution="PARSE")
    aggregate = runner.aggregate_samples(live[0]["case_id"], mixed, tmp_path / "mixed.json")
    assert aggregate["passed_count"] == 2 and aggregate["sample_count"] == 3
    assert aggregate["attribution_counts"] == {"PARSE": 1}
    report["rows"][next(i for i, row in enumerate(report["rows"]) if row["case_id"] == "B01")] = aggregate
    assert "mixed.json) | 2/3 |" in render_report(report)


def test_default_repeats_is_one_and_still_boolean(tmp_path, configured):
    report = evaluate(DATA, raw_dir=tmp_path, model="test-model", version="v3",
                      recognition_dir=ROOT / "docs/reports/raw/recognition_v2")
    assert report["repeats"] == 1
    assert all(isinstance(row["passed"], bool) for row in report["rows"])
    assert "硬性通过数：" in render_report(report)


@pytest.mark.parametrize("repeats", ["0", "-1", "1.5"])
def test_cli_rejects_invalid_repeats_before_network(repeats, monkeypatch, configured):
    monkeypatch.setattr("sys.argv", ["evaluate", "--repeats", repeats])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_repeat_cli_only_writes_v3(tmp_path, monkeypatch, configured):
    output = tmp_path / "eval_v3.md"
    monkeypatch.setattr("sys.argv", ["evaluate", "--repeats", "3", "--output", str(output),
                                     "--raw-dir", str(tmp_path / "raw"), "--recognition-dir",
                                     str(ROOT / "docs/reports/raw/recognition_v2")])
    assert main() == 0
    assert len(list((tmp_path / "raw/compose_v3").glob("B*.r*.json"))) == 30
    assert not (tmp_path / "raw/compose").exists()
    assert not (tmp_path / "raw/compose_v2").exists()
    assert "N=3" in output.read_text()


@pytest.mark.parametrize("filename", ["B07.r02.json", "B07.r04.json"])
def test_repeat_preflight_does_not_rerun_partial_samples(tmp_path, monkeypatch, configured, filename):
    import scripts.evaluate as runner

    path = tmp_path / "compose_v3" / filename
    path.parent.mkdir()
    path.write_text("existing")
    monkeypatch.setattr(runner, "run_compose_case", lambda *args, **kwargs: pytest.fail("已有证据时不能发新请求"))
    with pytest.raises(EvaluationInterrupted, match="已存在"):
        evaluate(DATA, raw_dir=tmp_path, model="test-model", version="v3", repeats=3,
                 recognition_dir=ROOT / "docs/reports/raw/recognition_v2")
    assert path.read_text() == "existing"


def test_b03_bench_correction_preserves_all_expectations():
    before = json.loads((ROOT / "docs/reports/raw/compose/B03.json").read_text())
    current = next(case for case in DATA["cases"] if case["id"] == "B03")
    assert current["expect"] == before["expect"]
    assert current["fail_policy"] == "BENCH"


def test_comparison_lists_every_green_to_red_case():
    from scripts.evaluate import compare_reports

    old = json.loads((ROOT / "docs/reports/eval_v1.json").read_text())
    new = deepcopy(old)
    rows = {row["case_id"]: row for row in new["rows"]}
    rows["R02"].update(passed=False, failure_reasons=["category"], attribution="IN")
    rows["B01"].update(passed=False, failure_reasons=["set_count"], attribution="COMPOSE")
    rows["R03"].update(passed=True, failure_reasons=[], attribution="—")
    rows["R03"]["checks"]["sub_in"] = True
    comparison = compare_reports(old, new)
    assert comparison["r03_turned_green"] is True
    assert comparison["sub_before"] == "8/9" and comparison["sub_after"] == "9/9"
    assert comparison["recognition_regressions"] == ["R02"]
    assert len(comparison["regressions"]) == 2
    assert comparison["regressions"][0].startswith("B01")
    assert comparison["regressions"][1].startswith("R02")


def test_cli_exposes_recognition_dir_and_v2_report(tmp_path, monkeypatch, configured):
    import scripts.evaluate as runner

    called = []
    original = runner.evaluate
    def observed(*args, **kwargs):
        called.append(kwargs["recognition_dir"])
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate", observed)
    from scripts.record_recognition import record_cases
    def injected(prompt, image, **kwargs):
        original = json.loads((ROOT / "docs/reports/raw/recognition" / f"R{int(image.stem[-2:]):02}.json").read_text())
        return original | {"attempts": [], "error": None}

    recordings = tmp_path / "recognition_v2"
    record_cases(DATA, out_dir=recordings, vision=injected)
    path = tmp_path / "eval_v2.md"
    monkeypatch.setattr("sys.argv", ["evaluate", "--recognition-dir", str(recordings),
                                     "--output", str(path), "--raw-dir", str(tmp_path / "raw_v2")])
    assert main() == 0
    assert called == [recordings]
    text = path.read_text()
    assert "评测跑批 v2" in text
    assert "v1 vs v2" in text
    assert "BENCH=" in text
    assert "sub_in" in text and "绿转红" in text


def test_replay_never_calls_model_and_preserves_r03(tmp_path, monkeypatch, configured):
    from app.services import extract

    calls = []
    original = extract.extract_record

    def observed(record):
        calls.append(record["case_id"])
        return original(record)

    monkeypatch.setattr(extract, "extract_record", observed)
    result = evaluate(DATA, raw_dir=tmp_path / "raw", model="test-model", secret="test-secret")
    assert calls == [f"R{i:02}" for i in range(1, 10)]
    rows = {row["case_id"]: row for row in result["rows"]}
    assert len(rows) == 24
    assert rows["R03"]["passed"] is False
    assert rows["R03"]["attribution"] == "IN"
    for name in ("B05", "B10"):
        assert rows[name]["passed"] is False
        assert rows[name]["attribution"] == "依赖未实现（T9）"
        assert rows[name]["attempts"]
    for name in ("C03", "C04", "C05"):
        assert rows[name]["passed"] is True
        assert rows[name]["source"] == "注入"
    assert rows["C03"]["checks"]["parse_retry_gte"] is True
    assert rows["C05"]["checks"]["validator_rejected"] is True
    assert rows["C05"]["checks"]["regenerate_count_gte"] is True
    assert rows["C04"]["checks"]["ui_shows_banner"] is True
    for index in range(1, 11):
        record = json.loads((tmp_path / "raw/compose" / f"B{index:02}.json").read_text())
        assert {"raw_content", "latency_ms", "degraded", "prompt_version", "timestamp"} <= record.keys()
        assert record["raw_content"]
        assert "test-secret" not in json.dumps(record)


def test_report_denominator_skips_sources_and_range_only(configured, tmp_path):
    report = evaluate(DATA, raw_dir=tmp_path / "raw", model="test-model", secret="test-secret")
    markdown = render_report(report)
    assert "分母：24" in markdown
    assert "重放自 2026-11-13 录制" in markdown
    assert "跳过：素材未备" in markdown
    assert "DASHSCOPE_MODEL：test-model" in markdown
    assert "未重做浏览器验收" in markdown
    assert "平均" not in markdown
    assert "min–max" in markdown and "n=9" in markdown and "n=10" in markdown
    assert sum(line.startswith("| [") for line in markdown.splitlines()) == 24


def test_exact_outer_and_reason_constraints_are_not_relaxed():
    filtered = filter_candidates(WARDROBE, temp_c=18, occasion="commute")
    result = fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
    checks = assert_composition({"outer_in": [], "reason_length_range": [1, 2]}, result, filtered, WARDROBE, {})
    assert checks == {"outer_in": False, "reason_length_range": False}
    with pytest.raises(EvaluationInterrupted, match="断言"):
        assert_composition({"unknown_assertion": True}, result, filtered, WARDROBE, {})


def test_missing_recognition_record_interrupts_before_live_calls(tmp_path, monkeypatch, configured):
    import scripts.evaluate as runner

    called = []
    monkeypatch.setattr(runner, "run_compose_case", lambda *args, **kwargs: called.append(True))
    with pytest.raises(EvaluationInterrupted):
        evaluate(DATA, raw_dir=tmp_path / "raw", recognition_dir=tmp_path / "missing", model="test-model")
    assert called == []


def test_changed_recognition_expectation_interrupts_before_live_calls(tmp_path, monkeypatch, configured):
    import scripts.evaluate as runner

    changed = deepcopy(DATA)
    next(case for case in changed["cases"] if case["id"] == "R03")["expect"]["sub_in"] = ["长裤"]
    called = []
    monkeypatch.setattr(runner, "run_compose_case", lambda *args, **kwargs: called.append(True))
    with pytest.raises(EvaluationInterrupted, match="录制源"):
        evaluate(changed, raw_dir=tmp_path, model="test-model")
    assert called == []


def test_live_pipeline_reaches_chat_after_filter_and_generation(tmp_path, monkeypatch, configured):
    import scripts.evaluate as runner

    calls = []
    real_filter, real_generate, real_chat = runner.filter_candidates, runner.generate_outfits, client.chat

    def filtering(*args, **kwargs):
        calls.append("filter")
        return real_filter(*args, **kwargs)

    def generating(*args, **kwargs):
        calls.append("generate")
        return real_generate(*args, **kwargs)

    def chatting(*args, **kwargs):
        calls.append("chat")
        return real_chat(*args, **kwargs)

    monkeypatch.setattr(runner, "filter_candidates", filtering)
    monkeypatch.setattr(runner, "generate_outfits", generating)
    monkeypatch.setattr(client, "chat", chatting)
    case = next(case for case in DATA["cases"] if case["id"] == "B01")
    row = run_compose_case(case, WARDROBE, raw_dir=tmp_path, model="test-model")
    assert row["source"] == "真实调用"
    assert calls == ["filter", "generate", "chat"]


def test_full_run_case_failures_still_exit_zero(tmp_path, monkeypatch, configured):
    output = tmp_path / "eval_v1.md"
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(output), "--raw-dir", str(tmp_path / "raw")])
    assert main() == 0
    assert output.exists()
    assert "R03" in output.read_text()


def test_all_network_failures_are_nonzero(tmp_path, monkeypatch, configured):
    real = httpx2.Client

    def fail(request):
        raise httpx2.ConnectError("test-secret", request=request)

    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(fail), **kwargs))
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(tmp_path / "eval.md"), "--raw-dir", str(tmp_path / "raw")])
    assert main() == 2


def test_real_parse_failure_cannot_pass_using_rule_fallback(tmp_path, monkeypatch, configured):
    real = httpx2.Client
    monkeypatch.setattr(client, "_http_client", lambda **kwargs: real(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(
            200, json={"choices": [{"message": {"content": "not JSON"}}]},
        )), **kwargs,
    ))
    case = next(case for case in DATA["cases"] if case["id"] == "B01")
    row = run_compose_case(case, WARDROBE, raw_dir=tmp_path, model="test-model")
    assert row["result"]["sets"]  # 产品有可用结果，模型硬性通过仍为否。
    assert row["degraded"] is True
    assert row["passed"] is False
    assert row["attribution"] == "PARSE"


def test_existing_report_not_overwritten_or_recalled(tmp_path, monkeypatch, configured):
    output = tmp_path / "eval_v1.md"
    output.write_text("original evidence")
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(output)])
    assert main() == 2
    assert output.read_text() == "original evidence"


@pytest.mark.parametrize("name", ["C01", "C02"])
def test_shortage_runs_filter_without_client_call(name, configured, tmp_path):
    case = next(case for case in DATA["cases"] if case["id"] == name)
    row = run_compose_case(case, WARDROBE, raw_dir=tmp_path, model="test-model", secret="test-secret")
    assert row["passed"] is True
    assert row["attempts"] == []
