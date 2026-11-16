import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.llm import client
from app.llm.errors import public_model_failure
from app.models import (
    CorrectionAudit,
    ErrorCategory,
    WardrobeItem,
    derive_needs_confirm,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL_FIELDS = frozenset(("category", "sub", "colors", "material", "pattern", "warmth",
                          "formality", "seasons", "confidence"))
# P1入口：sub自由生成会超出有限词表，应收敛枚举并映射同义词；证据见docs/reports/t11-repeatability.md，本阶段不改行为。
SPEC = json.loads((Path(__file__).resolve().parents[2] / "cases/cases.json").read_text())["meta"]["filter_spec"]


class ExtractError(Exception):
    def __init__(self, message, *, had_fences=None, status=422, code="IN_PARSE", category=None):
        super().__init__(message)
        self.code = code
        self.had_fences = had_fences
        self.status = status
        self.category = category


def strip_fences(raw: str) -> str:
    text = raw.strip()
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip().lower() in ("```json", "```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def apply_category_rules(item: WardrobeItem) -> tuple[WardrobeItem, list[str]]:
    values = item.model_dump()
    sources, corrections = dict(item.sources), []
    if item.category == "outer" and item.warmth is not None and item.warmth < 2:
        values["warmth"] = 2
        sources["warmth"] = "derived"
        corrections.append(f"warmth: {item.warmth} -> 2（outer 类目下限）")
    # 只用当前规则支持的关系收窄；D9 鞋类不能按 warmth 推断季节。
    if item.category not in SPEC.get("warmth_exempt_slots", ()) and values["warmth"] is not None:
        compatible = set()
        for band, (low, high) in SPEC["allowed_warmth"].items():
            if low <= values["warmth"] <= high:
                compatible.update(SPEC["allowed_seasons"][band])
        seasons = [season for season in item.seasons if season in compatible]
        if seasons != item.seasons:
            values["seasons"] = seasons
            sources["seasons"] = "derived"
            corrections.append(f"seasons: {item.seasons} -> {seasons}（filter_spec 一致性）")
    values["sources"] = sources
    return WardrobeItem.model_validate(values), corrections


def parse_items(raw: str, *, image_path: str) -> list[WardrobeItem]:
    """JSON 只负责语法解析；所有单品必须经唯一 WardrobeItem 协议校验。"""
    payload = json.loads(strip_fences(raw))
    if not isinstance(payload, dict) or set(payload) != {"items"} or not isinstance(payload["items"], list):
        raise ValueError("响应必须只包含 items 数组。")
    items = []
    for data in payload["items"]:
        if not isinstance(data, dict) or set(data) != MODEL_FIELDS:
            raise ValueError("单品必须包含完整九个识别字段，不能提供来源或系统字段。")
        if data["confidence"] is None:
            raise ValueError("confidence 必须由模型提供。")
        item = WardrobeItem.model_validate({**data, "id": "V" + uuid4().hex, "image_path": image_path})
        item.needs_confirm = derive_needs_confirm(uploaded=True, user_edited=item.user_edited)
        items.append(item)
    return items


def resolve_prompt_file(prompt_file: str) -> Path:
    allowed = {f"prompts/item_extract.v{version}.md" for version in (1, 2)}
    if prompt_file not in allowed:
        raise ValueError("prompt_file 只允许识别 v1/v2 的固定相对路径。")
    path = ROOT / prompt_file
    if path.resolve() != ROOT.resolve() / prompt_file:
        raise ValueError("prompt_file 不允许符号链接或路径跳转。")
    return path


def _recognition_failure(category):
    status, message = public_model_failure(category)
    if category == ErrorCategory.TIMEOUT:
        message = "识别超时，图片已保留。请重试，或稍后再试。"
    codes = {ErrorCategory.AUTH: "MODEL_CONFIG", ErrorCategory.TIMEOUT: "MODEL_TIMEOUT",
             ErrorCategory.PARSE: "MODEL_RESPONSE"}
    return ExtractError(message, status=status, code=codes.get(category, "MODEL_NETWORK"), category=category)


def extract_photo(image: Path, *, image_reference: str, mime_type: str, request_id: str, vision=None) -> list[WardrobeItem]:
    """上传与录制共用解析/校正规则；网络唯一出口仍为client.vision。"""
    prompt = resolve_prompt_file("prompts/item_extract.v2.md").read_text(encoding="utf-8")
    call = vision or client.vision
    try:
        result = call(prompt, image, model="qwen3.8-omni-flash", prompt_version="item_extract.v2",
                      case_id=request_id, timeout=20, max_retries=2, mime_type=mime_type,
                      validate=lambda raw: parse_items(raw, image_path=image_reference))
    except client.LLMError as error:
        raise _recognition_failure(error.category) from None
    if result.get("error"):
        raise _recognition_failure(ErrorCategory(result.get("category") or "network"))
    try:
        originals = parse_items(result["raw_content"], image_path=image_reference)
    except (ValueError, ValidationError):
        raise _recognition_failure(ErrorCategory.PARSE) from None
    if not originals:
        raise ExtractError("这张图里没有识别到衣物，换一张试试", code="NOT_CLOTHING")
    items = []
    for original in originals:
        corrected, corrections = apply_category_rules(original)
        values = corrected.model_dump()
        values["sources"]["_corrections"] = CorrectionAudit(entries=corrections)
        items.append(WardrobeItem.model_validate(values))
    return items


def extract_record(record: dict) -> dict:
    """重放已录制响应；不调用模型，原 checks/耗时不重新评定。"""
    prompt = resolve_prompt_file(record["prompt_file"]).read_text(encoding="utf-8")
    if sha256(prompt.encode("utf-8")).hexdigest()[:16] != record["prompt_sha256_prefix"]:
        raise ValueError("原始记录 prompt 哈希与当前文件不一致，禁止混用指标。")
    if (record["http_status"] != 200 or not isinstance(record.get("raw_content"), str)
            or (record.get("error") is not None and record.get("parse_ok") is False)):
        raise ExtractError("原始记录不是成功响应，不能伪装成识别成功。")
    raw = record["raw_content"]
    had_fences = strip_fences(raw) != raw.strip()
    if had_fences != record["had_fence"]:
        raise ValueError("围栏标记与原文不一致。")
    try:
        originals = parse_items(raw, image_path=record.get("image", ""))
    except (ValueError, ValidationError):
        raise ExtractError("原始响应的 JSON 或单品协议无效。", had_fences=had_fences) from None
    before = [item.model_dump(mode="json", include=MODEL_FIELDS) for item in originals]
    if {"items": before} != record["parsed"]:
        raise ValueError("解析结果与原始记录 parsed 不一致。")
    corrected, corrections = [], []
    for index, original in enumerate(originals):
        item, changes = apply_category_rules(original)
        corrected.append(item)
        corrections.extend(f"items[{index}].{change}" for change in changes)
    if record["checks"].get("sub_in") is False:
        corrections.append("sub 过泛或未命中原断言；保留模型原值，sub_in=False，不改写断言。")
    if not originals:
        actual = raw_actual = {"category": None, "reason": "NOT_CLOTHING"}
    else:
        after = [item.model_dump(mode="json", include=MODEL_FIELDS) for item in corrected]
        raw_actual = before[0] if len(before) == 1 else {"items": before}
        actual = after[0] if len(after) == 1 else {"items": after}
    return {"items": corrected, "actual": actual, "raw_actual": raw_actual,
            "status_code": 200 if originals else 422, "corrections": corrections,
            "checks": dict(record["checks"]), "had_fences": had_fences,
            "latency_ms": record["latency_ms"]}
