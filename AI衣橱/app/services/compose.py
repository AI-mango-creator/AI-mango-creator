import json
from functools import partial
from pathlib import Path
from time import perf_counter, sleep
from uuid import uuid4

from pydantic import ValidationError

from app.llm import client
from app.models import (
    ComposeFailure,
    ComposeResult,
    Composition,
    DegradeReason,
    ErrorCategory,
    Occasion,
    Shortage,
)
from app.services import fallback
from app.services.filter import count_composable_sets
from app.services.validate import validate_outfits

PROMPT_VERSION = "outfit_compose.v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / f"{PROMPT_VERSION}.md"


class ComposeError(Exception):
    def __init__(self, detail: ComposeFailure, *, category: ErrorCategory | None = None):
        super().__init__(detail.message)
        self.detail = detail
        self.category = category


def compose_outfits(
    filtered: dict, *, temp_c: int, occasion: Occasion,
    formality_target=None, case_id: str | None = None, chat=None,
) -> ComposeResult:
    """S3：缺件直返；正常路径调用真实 client；仅允许一次纠错重生成。"""
    started = perf_counter()
    if filtered["shortage"] is not None:
        shortage = Shortage.model_validate(filtered["shortage"])
        return ComposeResult(shortage=shortage, shortage_hint=shortage.message)
    candidates, band = filtered["candidates"], filtered["band"]
    expected_count = min(3, count_composable_sets(candidates, band))
    if expected_count == 0:
        raise ComposeError(ComposeFailure(
            attribution="COMPOSE", code="INVALID_OUTPUT", message="候选不足且缺少缺件信息，请重新筛选。",
        ))
    template = PROMPT_PATH.read_text(encoding="utf-8")
    system = template.replace("{{JSON_SCHEMA}}", json.dumps(Composition.model_json_schema(), ensure_ascii=False))
    if formality_target is None:
        case_data = json.loads((PROMPT_PATH.parents[1] / "cases/cases.json").read_text(encoding="utf-8"))
        formality_target = case_data["meta"]["filter_spec"]["occasion_formality"][occasion]
    payload = {
        "candidates": [item.model_dump(include={
            "id", "category", "colors", "warmth", "formality", "material",
        }) for item in candidates],
        "temp_c": temp_c, "band": band, "occasion": occasion,
        "formality_target": formality_target, "target_set_count": expected_count,
    }
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    call = client.chat if chat is None else chat
    with client.request_context(case_id=case_id or str(uuid4()), prompt_version=PROMPT_VERSION) as budget:
        for attempt in range(2):
            raw = None
            try:
                raw = call(messages, schema=Composition, timeout=20, max_retries=2)
            except client.LLMError as error:
                if error.code != "MODEL_RESPONSE":
                    raise ComposeError(ComposeFailure(
                        attribution="COMPOSE", code=error.code, message=str(error),
                    ), category=error.category) from None
                failures = [str(error)]
                attribution = "PARSE"
            else:
                try:
                    composition = Composition.model_validate_json(raw)
                    failures = validate_outfits(composition, candidates, band=band, expected_count=expected_count)
                    attribution = "COMPOSE"
                except ValidationError as error:
                    # 只反馈字段路径和类型；不反射原始输入、密钥或提供方错误内容。
                    failures = [f"{'.'.join(map(str, item['loc'])) or 'response'}: {item['type']}"
                                for item in error.errors(include_input=False, include_url=False, include_context=False)]
                    attribution = "PARSE"
            if not failures:
                return ComposeResult(
                    sets=composition.sets,
                    shortage_hint=f"符合条件的不同方案仅 {expected_count} 套。" if expected_count < 3 else None,
                    latency_ms=round((perf_counter() - started) * 1000),
                )
            if budget.attempts >= 3:
                break
            if attempt == 0:
                if raw is not None:
                    messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user", "content": f"{attribution} 校验失败：" + "；".join(failures)
                    + " 请修正这些问题并重新输出完整 JSON。",
                })
        raise ComposeError(ComposeFailure(
            attribution=attribution, code="INVALID_OUTPUT",
            message="模型未生成合规搭配，纠错次数或调用预算已用完，请稍后重试。", errors=failures,
        ), category=ErrorCategory.PARSE)


def generate_outfits(
    filtered: dict, *, temp_c: int, occasion: Occasion, formality_target=None,
    case_id: str | None = None, chat=None, wait=sleep, retry_delay=5,
) -> ComposeResult:
    """T7 的生产入口：仅捕获 S3 已归因失败；S1/S2/规则模板错误不降级。"""
    started = perf_counter()
    request_id = case_id or str(uuid4())
    call = chat if chat is not None else partial(client.chat, wait=wait, retry_delay=retry_delay)
    try:
        return compose_outfits(
            filtered, temp_c=temp_c, occasion=occasion, formality_target=formality_target,
            case_id=request_id, chat=call,
        )
    except ComposeError as error:
        reason = {
            ErrorCategory.AUTH: DegradeReason.AUTH,
            ErrorCategory.RATE_LIMIT: DegradeReason.RATE_LIMIT,
            ErrorCategory.TIMEOUT: DegradeReason.TIMEOUT,
            ErrorCategory.PARSE: DegradeReason.PARSE_FAILED,
        }.get(error.category)
        if reason is None:
            raise
        result = fallback.fallback_outfits(
            filtered["candidates"], band=filtered["band"], degrade_reason=reason,
        )
        result.latency_ms = round((perf_counter() - started) * 1000)
        client.log_degradation(case_id=request_id, prompt_version=PROMPT_VERSION,
                               latency_ms=result.latency_ms, reason=reason.value)
        return result
