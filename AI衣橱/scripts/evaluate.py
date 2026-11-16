"""T10 v1：真实组合、录制识别重放、客户端层失败注入。"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx2
from pydantic import ValidationError

from app.llm import client
from app.llm.errors import ServiceError
from app.models import Composition, ProviderCompletion, WardrobeItem
from app.services import extract
from app.services.compose import PROMPT_VERSION, ComposeError, generate_outfits
from app.services.fallback import fallback_outfits
from app.services.filter import filter_candidates

ROOT = Path(__file__).resolve().parents[1]
RECOGNITION = ROOT / "docs/reports/raw/recognition"
UI_EVIDENCE = ROOT / "docs/reports/ui-t7/03-degraded.png"
DEPENDENCIES = {"B05", "B10"}
# 录制源 commit 35e18aa 的 R01–R09 id/input/expect（排序 JSON、UTF-8）。
# 只核对用例身份与期望未漂移，不另造一套识别字段命中算法。
RECOGNITION_CASES_SHA256 = "1bdc81afa6485a26abdaca0ff687d07ce8f2b1b9eee5fa02e9051af7f5173edd"


class EvaluationInterrupted(Exception):
    pass


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def split_cases(data):
    expected = {f"{prefix}{number:02}" for prefix, limit in (("R", 9), ("B", 10), ("C", 5))
                for number in range(1, limit + 1)}
    pending = {f"A{number:02}" for number in range(1, 6)}
    cases = data["cases"]
    by_id = {case["id"]: case for case in cases}
    if len(cases) != 29 or len(by_id) != 29 or set(by_id) != expected | pending:
        raise EvaluationInterrupted("用例集合不是已确认的29条，不能静默调整24条分母。")
    if any(by_id[name]["input"].get("image_status") != "pending" for name in pending):
        raise EvaluationInterrupted("A类素材状态已变化，需人类确认新的评测范围。")
    if any(by_id[name]["input"].get("image_status") != "ready" for name in expected if name.startswith("R")):
        raise EvaluationInterrupted("R类素材状态与可跑范围不一致。")
    return [by_id[name] for name in sorted(expected)], [by_id[name] for name in sorted(pending)]


def _safe(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, dict):
        return {key: _safe(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item, secret) for item in value]
    return value


def _write_json(path, value, secret=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(value, secret), ensure_ascii=False, indent=2) + "\n")


class CaptureClient:
    """仅 C03–C05 替换客户端传输；B 类保留原真实传输。"""

    def __init__(self, case, filtered, secret):
        self.case, self.secret = case, secret
        self.attempts, self.feedback = [], []
        self.indices = {}
        self.inject = case["input"].get("inject")
        self.content = None
        if self.inject:
            legal = fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
            self.content = Composition(sets=legal.sets).model_dump_json()

    def on_request(self, request):
        self.indices[id(request)] = len(self.attempts)
        self.attempts.append({"timestamp": timestamp(), "http_status": None, "raw_content": None})
        messages = json.loads(request.content)["messages"]
        if len(self.attempts) > 1:
            self.feedback.append(_safe(messages[-1]["content"], self.secret))

    def on_response(self, response):
        response.read()
        entry = self.attempts[self.indices[id(response.request)]]
        entry["http_status"] = response.status_code
        try:
            envelope = ProviderCompletion.model_validate_json(response.text)
            entry["raw_content"] = _safe(envelope.choices[0].message.content, self.secret)
        except ValidationError:
            entry["error_body"] = _safe(response.text, self.secret)

    def injection(self, request):
        if self.inject == "llm_timeout":
            raise httpx2.ReadTimeout("评测注入：模拟模型20s未返回，不实际等待20s。", request=request)
        first = len(self.attempts) == 1
        content = self.content
        if first and self.inject == "llm_returns_fenced_json":
            content = f"```json\n{content}\n```"
        elif first and self.inject == "llm_duplicate_category_in_set":
            payload = Composition.model_validate_json(content).model_dump()
            slots = payload["sets"][0]["slots"]
            inputs = json.loads(json.loads(request.content)["messages"][1]["content"])
            slots["bottom"] = next(item["id"] for item in inputs["candidates"]
                                   if item["category"] == "top" and item["id"] != slots["top"])
            content = json.dumps(payload, ensure_ascii=False)
        return httpx2.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    def __enter__(self):
        original = client._http_client

        def factory(**kwargs):
            kwargs["event_hooks"] = {"request": [self.on_request], "response": [self.on_response]}
            if self.inject:
                return httpx2.Client(transport=httpx2.MockTransport(self.injection), **kwargs)
            return original(**kwargs)

        self.patch = patch.object(client, "_http_client", factory)
        self.patch.start()
        return self

    def __exit__(self, *args):
        self.patch.stop()


def assert_composition(expected, result, filtered, wardrobe, observations):
    sets = [outfit.slots.model_dump(exclude_none=True) for outfit in result.sets]
    all_ids = [item for slots in sets for item in slots.values()]
    by_id = {item.id: item for item in wardrobe}
    checks = {}
    status = "degraded" if result.degraded else "success"
    for name, value in expected.items():
        if name == "set_count":
            checks[name] = len(sets) == value
        elif name == "set_count_lt":
            checks[name] = len(sets) < value
        elif name == "set_count_lte":
            checks[name] = len(sets) <= value
        elif name == "set_count_gte":
            checks[name] = len(sets) >= value
        elif name == "all_items_in_wardrobe":
            checks[name] = (set(all_ids) <= set(by_id)) == value
        elif name == "no_duplicate_within_set":
            checks[name] = all(len(slots.values()) == len(set(slots.values())) for slots in sets) == value
        elif name == "must_not_use":
            checks[name] = not set(all_ids) & set(value)
        elif name == "must_use_any_of":
            checks[name] = all(set(slots.values()) & set(value) for slots in sets) and bool(sets)
        elif name == "must_have_categories":
            checks[name] = all(set(value) <= set(slots) for slots in sets) and bool(sets)
        elif name == "must_have_outer":
            checks[name] = all(("outer" in slots) == value for slots in sets) and bool(sets)
        elif name == "outer_in":
            checks[name] = bool(sets) and all(slots.get("outer") in value for slots in sets)
        elif name == "no_season_conflict":
            checks[name] = all(item in by_id and set(by_id[item].seasons)
                               & set(observations["filter_spec"]["allowed_seasons"][filtered["band"]])
                               for item in all_ids) == value
        elif name == "reason_must_mention_any_of":
            checks[name] = bool(result.sets) and all(any(word in outfit.reason for word in value) for outfit in result.sets)
        elif name == "reason_length_range":
            checks[name] = bool(result.sets) and all(value[0] <= len(outfit.reason) <= value[1] for outfit in result.sets)
        elif name == "must_emit_shortage_hint":
            checks[name] = bool(result.shortage_hint or result.shortage) == value
        elif name == "must_not_claim_warm":
            checks[name] = not result.sets and result.shortage is not None
        elif name == "distinct_sets_across_runs_gte":
            checks[name] = False  # T9 未实现；不拿普通重复生成替代 reroll。
        elif name in {"parse_retry_gte", "regenerate_count_gte"}:
            checks[name] = observations.get(name, 0) >= value
        elif name in {"validator_rejected", "ui_shows_banner"}:
            checks[name] = observations.get(name, False) == value
        elif name == "final_status":
            checks[name] = status == value
        elif name == "fallback_used":
            checks[name] = result.degraded == value
        elif name == "fallback_type":
            checks[name] = result.degraded and value == "rule_template"
        else:
            raise EvaluationInterrupted(f"未实现用例断言 {name}，不能静默忽略。")
    return checks


def evidence_path(raw_dir, case, version, sample_index=None):
    group = "compose" if case["id"].startswith("B") else "injections" if case["input"].get("inject") else "edges"
    suffix = "" if version == "v1" else "_" + version
    sample = f".r{sample_index:02}" if sample_index is not None else ""
    return Path(raw_dir) / (group + suffix) / f"{case['id']}{sample}.json"


def aggregate_samples(case_id, samples, path, secret=""):
    failures = [sample for sample in samples if not sample["passed"]]
    aggregate = {
        "case_id": case_id, "source": "真实调用", "timestamp": timestamp(),
        "sample_count": len(samples), "passed_count": sum(sample["passed"] for sample in samples),
        "degraded_count": sum(bool(sample["degraded"]) for sample in samples),
        "samples": samples, "attribution_counts": dict(Counter(sample["attribution"] for sample in failures)),
        "failure_reasons": [f"第{sample['sample_index']}次：" + "；".join(sample["failure_reasons"]) for sample in failures],
        "evidence": str(path),
    }
    _write_json(Path(path), aggregate, secret)
    return _safe(aggregate, secret)


def expand_samples(rows):
    return [sample for row in rows for sample in row.get("samples", [row])]


def result_summary(report):
    samples = expand_samples(report["rows"])
    if report.get("repeats", 1) == 1:
        return f"硬性通过数 {sum(row['passed'] for row in samples)} / 24"
    groups = {prefix: [row for row in samples if row["case_id"].startswith(prefix)] for prefix in ("R", "B", "C")}
    repeated = [row for row in report["rows"] if "passed_count" in row]
    stable = sum(1 for row in repeated if row["passed_count"] == row["sample_count"])
    return ("；".join(f"{label} {sum(row['passed'] for row in groups[prefix])}/{len(groups[prefix])}"
                      for prefix, label in (("B", "B累计通过"), ("R", "R单次录制"), ("C", "C单次规则/注入")))
            + f"；用例级稳定通过（{report['repeats']}次全过）{stable}/{len(repeated)}")


def run_compose_case(case, wardrobe, *, raw_dir, model, secret="", filter_spec=None, version="v1", sample_index=None):
    started, stamp = perf_counter(), timestamp()
    inputs = case["input"]
    arguments = {name: value for name, value in inputs.items()
                 if name in {"temp_c", "occasion", "formality_target", "excluded", "wardrobe_override"}}
    filtered = filter_candidates(wardrobe, **arguments)
    capture = CaptureClient(case, filtered, secret)
    result, error = None, None
    with capture:
        try:
            result = generate_outfits(filtered, temp_c=inputs["temp_c"], occasion=inputs["occasion"],
                                      formality_target=inputs.get("formality_target"),
                                      case_id=f"eval_{version}:{case['id']}" + (f":r{sample_index:02}" if sample_index else ""))
        except (ComposeError, client.LLMError, ServiceError) as failure:
            # 写清失败并继续其余用例；不会把异常记成通过。
            error = {"type": type(failure).__name__, "category": getattr(failure, "category", None),
                     "attribution": getattr(getattr(failure, "detail", None), "attribution", None)}
    elapsed = round((perf_counter() - started) * 1000)
    observations = {
        "parse_retry_gte": sum("PARSE 校验失败" in text for text in capture.feedback),
        "regenerate_count_gte": sum("COMPOSE 校验失败" in text for text in capture.feedback),
        "validator_rejected": any("COMPOSE 校验失败" in text for text in capture.feedback),
        "ui_shows_banner": bool(result and result.degraded and UI_EVIDENCE.is_file()),
        "filter_spec": filter_spec or json.loads((ROOT / "cases/cases.json").read_text())["meta"]["filter_spec"],
    }
    checks = (assert_composition(case["expect"], result, filtered, wardrobe, observations)
              if result is not None else dict.fromkeys(case["expect"], False))
    failed = [name for name, passed in checks.items() if not passed]
    attribution = "—" if not failed else case["fail_policy"]
    if error:
        attribution = error["attribution"] or ("PARSE" if error["category"] == "parse" else "COMPOSE")
        failed.append(f"生成异常：{error['type']}")
    if case["id"].startswith("B") and result and result.degraded:
        failed.append(f"真实编排降级：{result.degrade_reason}；基础搭配可用不等于模型通过")
        attribution = ("PARSE" if result.degrade_reason == "parse_failed"
                       and not observations["validator_rejected"] else "COMPOSE")
    if case["id"] in DEPENDENCIES:
        failed.append("依赖未实现（T9）；基础真实生成不等于排除交互/换一套验收")
        attribution = "依赖未实现（T9）"
    source = "注入" if inputs.get("inject") else "真实调用" if case["id"].startswith("B") else "纯规则边界"
    last = next((attempt for attempt in reversed(capture.attempts) if attempt["raw_content"] is not None), {})
    parsed = None
    if last.get("raw_content") is not None:
        try:
            parsed = Composition.model_validate_json(last["raw_content"]).model_dump(mode="json")
        except ValidationError:
            parsed = None  # 原始文本保留，parse_ok=False；不伪造解析结果。
    path = evidence_path(raw_dir, case, version, sample_index)
    row = {
        "case_id": case["id"], "timestamp": stamp, "model": model, "prompt_version": PROMPT_VERSION,
        "source": source, "input": inputs, "expect": case["expect"], "raw_content": last.get("raw_content"),
        "parsed": parsed, "parse_ok": parsed is not None,
        "http_status": capture.attempts[-1]["http_status"] if capture.attempts else None,
        "candidate_ids": [item.id for item in filtered["candidates"]],
        "band": filtered["band"], "composable_count": filtered["composable_count"],
        "latency_ms": elapsed, "degraded": result.degraded if result else None,
        "degrade_reason": result.degrade_reason if result else None,
        "result": result.model_dump(mode="json") if result else None, "checks": checks,
        "passed": not failed, "failure_reasons": failed, "attribution": attribution,
        "attempts": capture.attempts, "retry_feedback": capture.feedback,
        "error": error, "evidence": str(path),
    }
    if case["id"] == "C04":
        row["ui_evidence"] = str(UI_EVIDENCE)
    if sample_index is not None:
        row["sample_index"] = sample_index
    _write_json(path, row, secret)
    return _safe(row, secret)


def evaluate(data, *, raw_dir, model, secret="", recognition_dir=RECOGNITION, version="v1", repeats=1):
    if not isinstance(repeats, int) or repeats < 1:
        raise EvaluationInterrupted("repeats必须为正整数。")
    if repeats > 1 and version != "v3":
        raise EvaluationInterrupted("v1/v2官方基线保持N=1；重复采样只写v3。")
    if version == "v3" and not (ROOT / "docs/reports/t11-repeatability.md").is_file():
        raise EvaluationInterrupted("缺少识别重复采样结论报告。")
    started_at = timestamp()
    runnable, skipped = split_cases(data)
    recorded_cases = [{"id": case["id"], "input": case["input"], "expect": case["expect"]}
                      for case in runnable if case["id"].startswith("R")]
    fingerprint = sha256(json.dumps(recorded_cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if fingerprint != RECOGNITION_CASES_SHA256:
        raise EvaluationInterrupted("识别用例与录制源35e18aa的输入或期望不一致。")
    if not UI_EVIDENCE.is_file():
        raise EvaluationInterrupted("缺少已确认的 T7 黄条截图。")
    rows = []
    try:
        summary_path = Path(recognition_dir) / ("summary_v2.json" if version in ("v2", "v3") else "summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if version in ("v2", "v3") and summary["prompt_file"] != "prompts/item_extract.v2.md":
            raise EvaluationInterrupted("v2报告必须使用本轮v2真实识别录制，不能复用v1。")
        originals = {item["case_id"]: item for item in summary["records"]}
        for case in (case for case in runnable if case["id"].startswith("R")):
            path = Path(recognition_dir) / f"{case['id']}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["case_id"] != case["id"] or record["image"] != case["input"]["image"]:
                raise EvaluationInterrupted("识别用例与原文不一致。")
            if record["prompt_file"] != summary["prompt_file"]:
                raise EvaluationInterrupted("识别记录混用了不同prompt版本。")
            try:
                result = extract.extract_record(record)
            except extract.ExtractError:
                if version not in ("v2", "v3") or record.get("parse_ok") is not False:
                    raise
                # 超时/协议失败也是本轮真实识别结果，不能删样本或伪装为记录缺失。
                prompt = extract.resolve_prompt_file(record["prompt_file"]).read_bytes()
                if sha256(prompt).hexdigest()[:16] != record["prompt_sha256_prefix"]:
                    raise EvaluationInterrupted("失败记录prompt哈希不一致。")
                result = {"checks": record["checks"], "latency_ms": record["latency_ms"],
                          "had_fences": record["had_fence"], "raw_actual": {"error": record.get("error")}}
            canonical = originals[case["id"]]
            if (result["checks"] != canonical["checks"] or result["latency_ms"] != canonical["latency_ms"]
                    or result["had_fences"] != canonical["had_fence"]):
                raise EvaluationInterrupted("识别原文与汇总记录不一致。")
            names = [name for name, passed in result["checks"].items() if not passed]
            fields = {"sub_in": "sub", "color_in": "colors", "formality_range": "formality", "confidence_gte": "confidence"}
            failed = [f"{name}：实际 {result['raw_actual'].get(fields.get(name, name))}；期望 {case['expect'].get(name)}" for name in names]
            source = ("v2单次录制重放" if version == "v3" else "本轮真实识别" if version == "v2" else "重放自 2026-11-13 录制")
            rows.append({"case_id": case["id"], "source": source, "passed": not failed,
                         "failure_reasons": failed, "attribution": "IN" if failed else "—",
                         "latency_ms": record["latency_ms"], "checks": result["checks"],
                         "actual": result["raw_actual"], "evidence": str(path)})
    except (OSError, ValueError, KeyError, extract.ExtractError) as error:
        raise EvaluationInterrupted("识别记录缺失或与原文不一致；未开始真实组合调用。") from error
    raw_dir = Path(raw_dir)
    future_paths = []
    for case in (case for case in runnable if not case["id"].startswith("R")):
        future_paths.append(evidence_path(raw_dir, case, version))
        if repeats > 1 and case["id"].startswith("B"):
            future_paths.extend(evidence_path(raw_dir, case, version, index) for index in range(1, repeats + 1))
    if any(path.exists() for path in future_paths) or (version == "v3" and any(
            path for group in ("compose_v3", "edges_v3", "injections_v3")
            for path in (raw_dir / group).glob("*.json"))):
        raise EvaluationInterrupted("原始组合记录已存在，禁止覆盖或重新调用以美化报告。")
    wardrobe = [WardrobeItem.model_validate(item) for item in data["wardrobe"]]
    for case in (case for case in runnable if not case["id"].startswith("R")):
        print(f"评测 {case['id']} 开始…", flush=True)
        if repeats > 1 and case["id"].startswith("B"):
            samples = []
            for index in range(1, repeats + 1):
                sample = run_compose_case(case, wardrobe, raw_dir=raw_dir, model=model, secret=secret,
                                          filter_spec=data["meta"]["filter_spec"], version=version, sample_index=index)
                samples.append(sample)
                print(f"评测 {case['id']} 第{index}/{repeats}次：passed={sample['passed']} latency_ms={sample['latency_ms']} degraded={sample['degraded']}", flush=True)
            row = aggregate_samples(case["id"], samples, evidence_path(raw_dir, case, version), secret)
            print(f"评测 {case['id']} 完成：通过{row['passed_count']}/{repeats}", flush=True)
        else:
            row = run_compose_case(case, wardrobe, raw_dir=raw_dir, model=model, secret=secret,
                                   filter_spec=data["meta"]["filter_spec"], version=version)
            print(f"评测 {case['id']} 完成：passed={row['passed']} latency_ms={row['latency_ms']} degraded={row['degraded']}", flush=True)
        rows.append(row)
    live = [row for row in expand_samples(rows) if row["source"] == "真实调用"]
    any_live_response = any(attempt["http_status"] == 200 for row in live for attempt in row["attempts"])
    return {"timestamp": timestamp(), "started_at": started_at, "model": model, "prompt_version": PROMPT_VERSION, "denominator": 24,
            "repeats": repeats, "official_baseline": repeats == 1,
            "rows": rows, "skipped": skipped, "interrupted": not any_live_response,
            "interruption_reason": None if any_live_response else "全部真实组合均未获得模型200响应。",
            "recognition_model": summary["model"], "version": version,
            "recognition_prompt": summary["prompt_file"], "recognition_summary": str(summary_path)}


def _range(rows):
    values = [row["latency_ms"] for row in rows]
    return f"{min(values)}–{max(values)}ms, n={len(values)}" if values else "无样本, n=0"


def render_report(report):
    rows = report["rows"]
    repeats = report.get("repeats", 1)
    samples = expand_samples(rows)
    passed = sum(row["passed"] for row in samples) if repeats == 1 else None
    counts = Counter(row["attribution"] for row in samples if not row["passed"])
    version = report.get("version", "v1")
    recognition_prompt = Path(report.get("recognition_prompt", "item_extract.v1.md")).stem
    lines = [f"# 评测跑批 {version}", "", f"运行时间戳：{report['timestamp']}（Asia/Shanghai）",
             f"DASHSCOPE_MODEL：{report['model']}", f"prompt_version：{report['prompt_version']}；识别 {recognition_prompt}",
             "分母：24；用例集 v2 共29条。" if repeats == 1 else f"用例数：24；B类采样分母：10×{repeats}={10 * repeats}；R/C不重复。"]
    if version == "v3":
        lines.extend([f"采样设置：N={repeats}，只作用于B类；官方可比基线默认N=1。",
                      "识别侧重复实验中R02、R03各3次均通过2/3，单次差异不能作为稳定改进证据，因此本轮不重复识别（[结论来源](t11-repeatability.md)）。",
                      "R 类为单次录制，抖动区间见 [docs/reports/t11-repeatability.md](t11-repeatability.md)。",
                      f"本轮B采样时段：{report.get('started_at', report['timestamp'])} 至 {report['timestamp']}。"])
        if repeats > 1:
            lines.append("本报告为重复采样诊断；不按任一次成功或多数通过折为布尔，不与v1/v2单次硬性通过数相减。")
    lines.extend(["", "## 跳过：素材未备", ""])
    lines.extend(f"- {case['id']}：跳过：素材未备（image_status=pending），不计入分母。" for case in report["skipped"])
    recognition_source = ("R01–R09：读取既有v2单次录制，本轮只重放，不重新调用视觉模型。" if version == "v3" else
                          "R01–R09：本轮九张照片用item_extract.v2真实重新录制，评测读取本轮新原文，不复用v1。"
                          if version == "v2" else "R01–R09：重放自 2026-11-13 录制，未重新调用视觉模型。")
    lines.extend(["", "## 明细", "", recognition_source + "B01–B10：完整过滤→编排→真实客户端。",
                  "C01/C02：纯规则边界；C03–C05：客户端层注入，不计入真实模型失败。",
                  "C04 直接注入超时异常，未实际等待20s；注入耗时不能作为模型性能数据。",
                  "C04 UI黄条引用 [T7 截图](ui-t7/03-degraded.png)，未重做浏览器验收。",
                  (f"B05/B10各采样{repeats}轮基础真实生成，均因T9未实现记失败；重复采样不等于换一套验收。" if repeats > 1
                   else "B05/B10 只保留一次基础真实生成，不以普通重复生成冒充 T9。"),
                  "B类若实际降级，即使基础搭配可用，仍记硬性失败并保留模型侧归因。", "",
                  "| case_id | 结果（B为通过次数/N） | 失败原因 | 归因 | 耗时 |" if repeats > 1 else "| case_id | 通过 | 失败原因 | 归因 | 耗时 |",
                  "|---|---|---|---|---|"])
    for row in rows:
        reason = "；".join(row["failure_reasons"]) or "—"
        if "outer_in" in row["failure_reasons"] and row.get("result"):
            actual = [outfit["slots"].get("outer") for outfit in row["result"]["sets"]]
            reason = reason.replace("outer_in", f"outer_in：实际外套 {actual}；只允许 {row['expect']['outer_in']}")
        reason = reason.replace("|", "\\|").replace("\n", " ")
        link = os.path.relpath(row["evidence"], ROOT / "docs/reports")
        if "samples" in row:
            score = f"{row['passed_count']}/{row['sample_count']}"
            attribution = "；".join(f"{name}×{count}" for name, count in row["attribution_counts"].items()) or "—"
            duration = _range(row["samples"])
        else:
            score, attribution, duration = "是" if row["passed"] else "否", row["attribution"], f"{row['latency_ms']}ms（n=1）"
        lines.append(f"| [{row['case_id']}]({link}) | {score} | {reason} | {attribution} | {duration} |")
    if version == "v2":
        comparison = report["comparison"]
        lines.extend(["", "## v1 vs v2", "", "| 指标 | v1 | v2 |", "|---|---|---|",
                      f"| R03 | {comparison['r03_before']} | {comparison['r03_after']} |",
                      f"| sub_in命中 | {comparison['sub_before']} | {comparison['sub_after']} |",
                      f"| 硬性通过数 | {comparison['passed_before']}/24 | {passed}/24 |",
                      "",
                      f"R03是否转绿：{'是' if comparison['r03_turned_green'] else '否'}；总通过数变化：{passed - comparison['passed_before']:+d}。",
                      "绿转红：" + ("；".join(comparison["regressions"]) or "无") + "。",
                      "识别绿转红：" + ("、".join(comparison["recognition_regressions"]) or "无") + "。",
                      "B03归因按本轮更正为BENCH，expect与v1不变；v1报告及原文冻结，仍为20/24。",
                      "v2识别走client.vision、20s超时、temperature=0；v1录制脚本为120s且未显式设温度，变化不能全部归于prompt。",
                      "编排prompt未改；B类重复采样产生的变动另列，不能当作识别prompt效果。",
                      "Prompt只追加：sub 必须给具体款型名，禁止使用「长裤 / 裤子 / 上衣 / 外套 / 鞋子」等上位词；其余一字不改。"])
        if comparison["model_boundary"]:
            lines.append("模型能力边界：R03在v2仍返回上位词；保留失败，不再出v3调参。")
    lines.extend(["", "## 汇总", "", f"硬性通过数：{passed} / 24。" if repeats == 1 else result_summary(report) + "。",
                  ("归因计数（B按失败样本计）：" if repeats > 1 else "归因计数：") + "；".join(f"{name}={counts.get(name, 0)}" for name in ("IN", "FILTER", "COMPOSE", "PARSE", "BENCH", "依赖未实现（T9）")) + "。",
                  ("识别本轮录制耗时（min–max）：" if version == "v2" else "识别原录制耗时（min–max）：") + _range([row for row in rows if row["case_id"].startswith("R")]),
                  "组合真实链路耗时（min–max）：" + _range([row for row in samples if row["source"] == "真实调用"]),
                  "规则边界耗时（min–max）：" + _range([row for row in rows if row["source"] == "纯规则边界"]),
                  "客户端注入耗时（min–max）：" + _range([row for row in rows if row["source"] == "注入"])])
    if repeats > 1:
        lines.append("官方单次基线不因本报告改变：v1/v2 仍为 20/24（N=1）；本报告为调用级诊断，不与基线相减、不替换简历主口径。")
    if report["interrupted"]:
        lines.extend(["", "执行中断：" + report["interruption_reason"]])
    return "\n".join(lines) + "\n"


def compare_reports(baseline, current):
    old = {row["case_id"]: row for row in baseline["rows"]}
    new = {row["case_id"]: row for row in current["rows"]}
    if set(old) != set(new) or len(old) != 24:
        raise EvaluationInterrupted("对照报告的24条用例身份不一致。")
    def sub_count(rows):
        values = [row["checks"].get("sub_in", False) for name, row in rows.items() if name.startswith("R")]
        return f"{sum(values)}/{len(values)}"
    regressions = [f"{name}（{';'.join(new[name]['failure_reasons'])}，{new[name]['attribution']}）"
                   for name in sorted(old) if old[name]["passed"] and not new[name]["passed"]]
    return {"passed_before": sum(row["passed"] for row in old.values()),
            "sub_before": sub_count(old), "sub_after": sub_count(new),
            "r03_before": "通过" if old["R03"]["passed"] else "失败",
            "r03_after": "通过" if new["R03"]["passed"] else "失败",
            "r03_turned_green": not old["R03"]["passed"] and new["R03"]["passed"],
            "regressions": regressions,
            "recognition_regressions": [name for name in sorted(old) if name.startswith("R") and old[name]["passed"] and not new[name]["passed"]],
            "model_boundary": new["R03"].get("actual", {}).get("sub") in ("长裤", "裤子", "上衣", "外套", "鞋子")}


def main():
    parser = argparse.ArgumentParser(description="真实组合评测；有用例失败仍产出报告并exit0，禁止覆盖已有证据。")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/reports/eval_v1.md")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "docs/reports/raw")
    parser.add_argument("--recognition-dir", type=Path, default=RECOGNITION)
    parser.add_argument("--repeats", type=int, default=1, help="仅B类真实重复采样次数，官方基线默认1；大于1只写eval_v3。")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats必须为正整数。")
    manifest = args.output.with_suffix(".json")
    try:
        if args.output.exists() or manifest.exists():
            raise EvaluationInterrupted("报告已存在，不覆盖原证据；请为新一轮选择新版本。")
        key, _, model = client._configuration()
        cases_path = ROOT / "cases/cases.json"
        data = json.loads(cases_path.read_text(encoding="utf-8"))
        version = {"eval_v2": "v2", "eval_v3": "v3"}.get(args.output.stem, "v1")
        baseline = None
        if version == "v2":
            baseline = json.loads((ROOT / "docs/reports/eval_v1.json").read_text(encoding="utf-8"))
            runnable, _ = split_cases(data)
            if {row["case_id"] for row in baseline["rows"]} != {case["id"] for case in runnable}:
                raise EvaluationInterrupted("v1对照记录缺失或用例不匹配。")
        report = evaluate(data, raw_dir=args.raw_dir, model=model, secret=key,
                          recognition_dir=args.recognition_dir, version=version, repeats=args.repeats)
        if baseline is not None:
            report["comparison"] = compare_reports(baseline, report)
        report["cases_sha256"] = sha256(cases_path.read_bytes()).hexdigest()
        _write_json(manifest, report, key)
        args.output.write_text(render_report(report), encoding="utf-8")
        print(f"报告：{args.output}；{result_summary(report)}", flush=True)
        return 2 if report["interrupted"] else 0
    except (EvaluationInterrupted, OSError, ValueError, KeyError, client.LLMError):
        print("跑批中断：请检查记录完整性、配置、原文一致性或报告是否已经存在。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
