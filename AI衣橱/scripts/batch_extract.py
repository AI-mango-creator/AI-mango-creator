"""离线重放真实录制原文；不联网、不内置 prompt、不另算一套指标。"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

from app.services.extract import ExtractError, extract_record

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "docs/reports/raw/recognition"
COLUMNS = ["case_id", "真值", "实际", "逐字段一致", "耗时", "是否含围栏", "corrections"]


def select_ready_cases(data):
    ids = {f"R{index:02}" for index in range(1, 10)}
    return sorted((case for case in data["cases"] if case["id"] in ids
                   and case["input"].get("image_status") == "ready"), key=lambda case: case["id"])


async def run_batch(cases, *, records_dir=RECORDS, process=None):
    semaphore = asyncio.Semaphore(3)

    async def run(case):
        async with semaphore:
            text = await asyncio.to_thread((Path(records_dir) / f"{case['id']}.json").read_text, encoding="utf-8")
            source = json.loads(text)
            if source["case_id"] != case["id"] or source["image"] != case["input"]["image"]:
                raise ValueError("用例与原始记录的 id/image 不一致。")
            result = (await asyncio.to_thread(extract_record, source) if process is None else await process(source))
            sources = [item.sources for item in result["items"]]
            return {"case_id": case["id"], "真值": case["expect"],
                    "实际": {"source": "recorded_response", "raw": result["raw_actual"],
                           "corrected": result["actual"], "sources": sources},
                    "逐字段一致": result["checks"], "耗时": result["latency_ms"],
                    "是否含围栏": result["had_fences"], "corrections": result["corrections"]}

    # gather 按输入顺序返回；并发完成先后不会改变 CSV 用例顺序。
    return await asyncio.wait_for(asyncio.gather(*(run(case) for case in cases)), timeout=90)


def write_report(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: (json.dumps(row[name], ensure_ascii=False) if not isinstance(row[name], str)
                                    else row[name]) for name in COLUMNS})


def main():
    parser = argparse.ArgumentParser(description="离线重放 ready R01–R09，CSV 保留原 checks；R03 失败不修饰。")
    parser.add_argument("--cases", type=Path, default=ROOT / "cases/cases.json")
    parser.add_argument("--records", type=Path, default=RECORDS)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/reports/eval_vision.csv")
    args = parser.parse_args()
    try:
        data = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = select_ready_cases(data)
        if not cases:
            raise ValueError("没有 ready 的 R01–R09，未生成空报告。")
        summary = json.loads((args.records / "summary.json").read_text(encoding="utf-8"))
        rows = asyncio.run(run_batch(cases, records_dir=args.records))
        if [row["case_id"] for row in rows] != [entry["case_id"] for entry in summary["records"]]:
            raise ValueError("summary 与本次 ready 用例集合不一致，不引用不对应的指标。")
        for row, entry in zip(rows, summary["records"]):
            if (row["逐字段一致"] != entry["checks"] or row["耗时"] != entry["latency_ms"]
                    or row["是否含围栏"] != entry["had_fence"]):
                raise ValueError("summary 与原始记录内容不一致。")
        write_report(args.output, rows)
    except (OSError, ValueError, KeyError, TimeoutError, ExtractError):
        print("离线跑批失败：请检查原始记录、prompt 哈希、用例和 summary 是否一致。", file=sys.stderr)
        return 2
    print(f"离线重放（不是新模型调用）：用例 {summary['cases']} | HTTP 200 {summary['http_ok']}/{summary['cases']} | "
          f"解析 {summary['parse_ok']}/{summary['cases']} | 用例通过 {summary['case_pass']}/{summary['cases']}")
    print(f"原始围栏 {summary['fence_count']}/{summary['cases']} ({summary['fence_rate']:.0%}) | "
          f"单张平均 {summary['latency_ms']['mean']}ms | 原并发3墙钟 {summary['wall_ms']}ms")
    for field, stat in summary["field_accuracy"].items():
        print(f"{field}: {stat['hit']}/{stat['total']}")
    return int(summary["case_pass"] != summary["cases"])


if __name__ == "__main__":
    raise SystemExit(main())
