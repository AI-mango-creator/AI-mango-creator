"""T11 v2 真实录制；网络只走 client.vision，所有 v1 证据保持只读。"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path

from app.llm import client
from app.services.extract import parse_items, resolve_prompt_file, strip_fences

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3.8-omni-flash"
PROMPT_FILE = "prompts/item_extract.v2.md"
OUT_DIR = ROOT / "docs/reports/raw/recognition_v2"


def write_new(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def compare(item: dict, expect: dict) -> dict:
    """逐字段比对；断言口径与 cases.json 的 expect 键一致。"""
    checks = {}

    def color_hit() -> bool:
        wanted = expect.get("color_in") or []
        return any(any(w in c or c in w for w in wanted) for c in item.get("colors") or [])

    if "category" in expect:
        checks["category"] = item.get("category") == expect["category"]
    if "sub_in" in expect:
        sub = str(item.get("sub") or "")
        checks["sub_in"] = any(token in sub or sub in token for token in expect["sub_in"])
    if "color_in" in expect:
        checks["color_in"] = color_hit()
    if "formality_range" in expect:
        low, high = expect["formality_range"]
        value = item.get("formality")
        checks["formality_range"] = isinstance(value, int) and low <= value <= high
    if "confidence_gte" in expect:
        value = item.get("confidence")
        checks["confidence_gte"] = isinstance(value, (int, float)) and value >= expect["confidence_gte"]
    if "pattern" in expect:
        checks["pattern"] = item.get("pattern") == expect["pattern"]
    return checks



def record_cases(data, *, out_dir=OUT_DIR, vision=None):
    vision = vision or client.vision
    out_dir = Path(out_dir).resolve()
    frozen = (ROOT / "docs/reports/raw/recognition").resolve()
    if out_dir == frozen or out_dir.is_relative_to(frozen):
        raise ValueError("v1 录制目录冻结，不允许写入。")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("录制目录已存在证据，不覆盖、不自动重跑。")
    cases = sorted((c for c in data["cases"] if c["id"].startswith("R")
                    and c["input"].get("image_status") == "ready"), key=lambda c: c["id"])
    if [c["id"] for c in cases] != [f"R{i:02}" for i in range(1, 10)]:
        raise ValueError("本轮必须完整录制R01–R09。")
    prompt = resolve_prompt_file(PROMPT_FILE).read_text(encoding="utf-8")
    images = [(ROOT / "cases" / c["input"]["image"]).resolve() for c in cases]
    if any(not path.is_relative_to((ROOT / "cases/images").resolve()) or not path.is_file() for path in images):
        raise ValueError("识别素材缺失或路径超出cases/images。")
    out_dir.mkdir(parents=True, exist_ok=True)

    def work(case):
        image = ROOT / "cases" / case["input"]["image"]
        result = vision(prompt, image, model=MODEL, prompt_version="item_extract.v2", case_id="eval_v2:" + case["id"],
                        timeout=20, max_retries=2, validate=lambda raw: parse_items(raw, image_path=case["input"]["image"]))
        raw = result.get("raw_content")
        record = {"case_id": case["id"], "title": case.get("title"), "image": case["input"]["image"],
                  "image_bytes": image.stat().st_size, "model": MODEL, "prompt_file": PROMPT_FILE,
                  "prompt_version": "item_extract.v2", "prompt_sha256_prefix": sha256(prompt.encode()).hexdigest()[:16],
                  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                  **{key: result.get(key) for key in ("http_status", "raw_content", "latency_ms", "attempts", "error", "category")},
                  "had_fence": bool(raw and strip_fences(raw) != raw.strip()), "parse_ok": False,
                  "parsed": None, "checks": dict.fromkeys(case["expect"], False)}
        if record.get("http_status") == 200 and raw and record.get("error") is None:
            try:
                items = parse_items(raw, image_path=case["input"]["image"])
                record["parsed"] = json.loads(strip_fences(raw))
                record["parse_ok"] = True
                record["item_count"] = len(items)
                record["checks"] = compare(record["parsed"]["items"][0], case["expect"]) if items else {"item_count": False}
            except ValueError:
                record["parse_error"] = "JSON或单品字段校验失败，原文已保留。"
        record["passed"] = record["parse_ok"] and all(record["checks"].values())
        write_new(out_dir / f"{case['id']}.json", record)
        print(f"真实识别 {case['id']}: passed={record['passed']} latency_ms={record['latency_ms']}", flush=True)
        return record

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(work, cases))
    ok = [r for r in records if r.get("http_status") == 200]
    totals = {}
    for r in records:
        for field, passed in r["checks"].items():
            totals.setdefault(field, []).append(bool(passed))
    latencies = [r["latency_ms"] for r in ok]
    summary = {"model": MODEL, "prompt_file": PROMPT_FILE, "cases": len(records), "http_ok": len(ok),
               "fence_count": sum(bool(r["had_fence"]) for r in ok),
               "fence_rate": round(sum(bool(r["had_fence"]) for r in ok) / max(len(ok), 1), 4),
               "parse_ok": sum(bool(r["parse_ok"]) for r in ok), "case_pass": sum(bool(r["passed"]) for r in records),
               "latency_ms": {"min": min(latencies, default=0), "max": max(latencies, default=0),
                              "mean": round(sum(latencies) / max(len(latencies), 1))},
               "concurrency": 3, "wall_ms": round((time.perf_counter() - started) * 1000),
               "field_accuracy": {field: {"hit": sum(values), "total": len(values),
                                            "rate": round(sum(values) / len(values), 4)} for field, values in sorted(totals.items())},
               "records": [{key: r.get(key) for key in ("case_id", "passed", "latency_ms", "had_fence", "checks")} for r in records]}
    write_new(out_dir / "summary_v2.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="R01–R09 v2真实录制，禁止覆盖v1或已有v2。")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    try:
        data = json.loads((ROOT / "cases/cases.json").read_text(encoding="utf-8"))
        summary = record_cases(data, out_dir=args.output_dir)
    except (OSError, ValueError, KeyError, client.LLMError):
        print("录制中断：请检查配置、素材与目录；已留存原文不覆盖。", file=sys.stderr)
        return 2
    print(f"真实识别：{summary['case_pass']}/9；sub_in={summary['field_accuracy']['sub_in']['hit']}/9；"
          f"耗时 {summary['latency_ms']['min']}–{summary['latency_ms']['max']}ms, n=9；墙钟{summary['wall_ms']}ms", flush=True)
    return 0 if summary["http_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
