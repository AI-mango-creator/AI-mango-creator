"""一次性真实端到端验证：28℃ 周末场景（D9 鞋类豁免修复后的直击场景）。

进程内起 uvicorn -> 真实 HTTP 请求 -> 真实模型调用 -> 真实写库。
不依赖后台进程，避免沙箱隔离导致的 SQLite 写失败。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_env() -> dict[str, str]:
    """把 .env 读进 os.environ（不覆盖已有值）。"""
    loaded = {}
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        loaded[key] = value
        os.environ.setdefault(key, value)
    return {k: ("***" if "KEY" in k.upper() else v) for k, v in loaded.items()}


def main() -> int:
    print("env:", load_env())

    from app.main import app  # 必须在 env 载入之后

    port = 8021
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(60):
        try:
            if httpx.get(f"{base}/api/wardrobe/items", timeout=1.0).status_code == 200:
                ready = True
                break
        except (httpx.TransportError, httpx.HTTPStatusError):
            # 服务尚未就绪，继续轮询
            pass
        time.sleep(0.5)
    if not ready:
        print("FAIL: 服务未就绪")
        return 1

    items = httpx.get(f"{base}/api/wardrobe/items", timeout=10).json()
    shoes = [(i["id"], i["sub"], i["warmth"]) for i in items if i["category"] == "shoes"]
    print(f"衣柜 {len(items)} 件，鞋 {shoes}")

    started = time.perf_counter()
    response = httpx.post(
        f"{base}/api/outfits",
        json={"temp_c": 28, "occasion": "weekend"},
        timeout=180.0,
    )
    wall = round((time.perf_counter() - started) * 1000)

    print(f"HTTP {response.status_code}  墙钟 {wall}ms")
    payload = response.json()

    # 先落盘原始响应，避免解析失败丢掉证据
    out = Path("/tmp/outfit28.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("原始响应已存:", out)

    if response.status_code != 200:
        print(json.dumps(payload, ensure_ascii=False)[:800])
        server.should_exit = True
        return 1

    print(
        f"status={payload.get('status')} degraded={payload.get('degraded')} "
        f"latency_ms={payload.get('latency_ms')} "
        f"degrade_reason={payload.get('degrade_reason')} prompt={payload.get('prompt_version')}"
    )
    shortage = payload.get("shortage")
    print("shortage:", json.dumps(shortage, ensure_ascii=False)[:200] if shortage else None)
    print("shortage_hint:", payload.get("shortage_hint"))

    names = {i["id"]: i for i in items}
    all_shoes = []
    for st in payload.get("sets", []):
        slots = st["slots"]
        picked = " + ".join(f"{slot}:{item_id}" for slot, item_id in slots.items())
        print(f"--- rank {st['rank']}: {picked}")
        print("    理由:", st["reason"][:140])
        if "shoes" in slots:
            all_shoes.append((slots["shoes"], names.get(slots["shoes"], {}).get("sub")))

    print(f"\n鞋位命中: {all_shoes}  套数={len(payload.get('sets', []))}")
    print(f"候选集件数={len(items)}（含 4 双鞋）")

    server.should_exit = True
    thread.join(timeout=5)
    return 0 if payload.get("sets") else 2


if __name__ == "__main__":
    raise SystemExit(main())
