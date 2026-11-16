"""P0 唯一模型出口；视觉与文本分别调用，不在导入时读取密钥。"""

import base64
import json
import os
import shlex
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter, sleep
from uuid import uuid4

import httpx2
from pydantic import BaseModel, ValidationError

from app.llm.errors import LLMError, classify_response_error
from app.models import ErrorCategory, ProviderCompletion

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
LOG_PATH = Path(os.getenv("APP_DATA_DIR", ROOT / "data")) / "llm.log"
_http_client = httpx2.Client


@dataclass
class _Request:
    case_id: str
    prompt_version: str
    attempts: int = 0
    rate_retries: int = 0


_request: ContextVar[_Request | None] = ContextVar("llm_request", default=None)


@contextmanager
def request_context(*, case_id: str, prompt_version: str):
    """网络重试和 S3 重生成共享每次生成最多三次的预算。"""
    token = _request.set(_Request(case_id, prompt_version))
    try:
        yield _request.get()
    finally:
        _request.reset(token)


def _configuration() -> tuple[str, str, str]:
    values = {}
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        for line in lines:
            tokens = shlex.split(line, comments=True)
            if tokens and tokens[0] == "export":
                tokens = tokens[1:]
            if len(tokens) == 1 and "=" in tokens[0]:
                name, value = tokens[0].split("=", 1)
                values[name] = value
    except (OSError, ValueError):
        raise LLMError("MODEL_CONFIG", "无法读取 .env，请检查文件权限与引号。") from None
    names = ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_MODEL")
    result = tuple(os.environ.get(name, values.get(name, "")).strip() for name in names)
    for name, value in zip(names, result):
        if not value or value.startswith(("your-", "<")):
            raise LLMError("MODEL_CONFIG", f"请先在 .env 配置 {name}，再调用模型。")
    try:
        url = httpx2.URL(result[1])
    except httpx2.InvalidURL:
        raise LLMError("MODEL_CONFIG", "DASHSCOPE_BASE_URL 地址格式无效。") from None
    if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
        raise LLMError("MODEL_CONFIG", "DASHSCOPE_BASE_URL 必须是无凭据、无查询参数的 HTTPS 地址。")
    return result


def _write_log(record):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        raise LLMError("MODEL_CONFIG", "模型调用日志无法写入，请检查 data 目录权限。") from None


def _log(context, started, usage, outcome, failure=None):
    record = {
        "case_id": context.case_id, "prompt_version": context.prompt_version,
        "latency_ms": round((perf_counter() - started) * 1000),
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "degraded": False, "outcome": outcome, "event": "model_call",
        "category": failure.category.value if failure else None,
        "http_status": failure.http_status if failure else None,
        "provider_code": failure.provider_code if failure else None,
        "diagnostic": failure.diagnostic if failure else None,
    }
    _write_log(record)


def log_degradation(*, case_id, prompt_version, latency_ms, reason):
    _write_log({
        "event": "fallback", "case_id": case_id, "prompt_version": prompt_version,
        "latency_ms": latency_ms, "prompt_tokens": None, "completion_tokens": None,
        "degraded": True, "degrade_reason": reason,
    })


def chat(messages, *, schema: type[BaseModel], timeout=20, max_retries=2, wait=sleep, retry_delay=5) -> str:
    """返回经协议校验的内容文本；业务内容由 S3 使用同一 schema 解析。"""
    context = _request.get()
    if context is None:
        with request_context(case_id=str(uuid4()), prompt_version="outfit_compose.v1"):
            return chat(messages, schema=schema, timeout=timeout, max_retries=max_retries,
                        wait=wait, retry_delay=retry_delay)
    key, base_url, model = _configuration()
    if not 0 < timeout <= 20 or not 0 <= max_retries <= 2:
        raise LLMError("MODEL_CONFIG", "模型超时必须在 0–20 秒内，重试次数必须在 0–2 内。")
    if retry_delay < 0:
        raise LLMError("MODEL_CONFIG", "限流等待时间不能为负数。")
    pending = [dict(message) for message in messages]
    for retry in range(max_retries + 1):
        if context.attempts >= 3:
            raise LLMError("MODEL_NETWORK", "本次编排已用完三次模型调用预算。")
        context.attempts += 1
        started, usage, outcome = perf_counter(), None, "MODEL_NETWORK"
        failure = None
        try:
            with _http_client(timeout=timeout, follow_redirects=False) as transport:
                response = transport.post(
                    base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": model, "messages": pending, "temperature": 0.3,
                        "max_tokens": 2048, "enable_thinking": False,
                        "response_format": {"type": "json_schema", "json_schema": {
                            "name": schema.__name__, "strict": True,
                            "schema": schema.model_json_schema(),
                        }},
                    },
                )
            if response.status_code != 200:
                failure = classify_response_error(response.status_code, response.text)
                outcome = failure.category.value
                if failure.category == ErrorCategory.RATE_LIMIT:
                    if context.rate_retries >= 1:
                        raise failure
                elif response.status_code < 500:
                    raise failure
            else:
                envelope = ProviderCompletion.model_validate_json(response.text)
                usage = envelope.usage
                if envelope.choices[0].finish_reason not in (None, "stop"):
                    outcome = "MODEL_RESPONSE"
                    failure = LLMError(outcome, "模型输出未完整结束，请重新生成。")
                    raise failure
                outcome = "ok"
                return envelope.choices[0].message.content
        except httpx2.TimeoutException:
            outcome = "MODEL_TIMEOUT"
            failure = LLMError(outcome, "模型响应超过时限，请稍后再试。")
            raise failure from None
        except httpx2.RequestError:
            failure = LLMError("MODEL_NETWORK", "无法连接模型服务，请检查网络后重试。")
        except ValidationError:
            outcome = "MODEL_RESPONSE"
            failure = LLMError(outcome, "模型服务响应格式无效。")
            raise failure from None
        finally:
            _log(context, started, usage, outcome, failure)
        if retry == max_retries or context.attempts >= 3:
            raise failure
        if failure.category == ErrorCategory.RATE_LIMIT:
            context.rate_retries += 1
            wait(retry_delay)
        pending.append({"role": "user", "content": f"上次调用失败：{failure} 请基于原始输入重新生成。"})
    raise LLMError("MODEL_NETWORK", "模型服务暂不可用。")


def vision(prompt, image, *, model, prompt_version, case_id, validate,
           timeout=20, max_retries=2, wait=sleep, retry_delay=5, mime_type="image/jpeg"):
    """视觉唯一出口；保留失败原文，结构错误带原因重试，超时/未授权立即停止。"""
    key, base_url, _ = _configuration()
    if not 0 < timeout <= 20 or not 0 <= max_retries <= 2 or retry_delay < 0:
        raise LLMError("MODEL_CONFIG", "视觉调用必须满足20秒、最多重试2次且等待非负。")
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        raise LLMError("MODEL_CONFIG", "视觉调用只支持JPG、PNG或WebP照片。")
    image_data = base64.b64encode(Path(image).read_bytes()).decode("ascii")
    pending = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64," + image_data}},
    ]}]
    attempts, total_started = [], perf_counter()
    with request_context(case_id=case_id, prompt_version=prompt_version):
        context = _request.get()
        for retry in range(max_retries + 1):
            context.attempts += 1
            started, usage, failure = perf_counter(), None, None
            raw, status = None, None
            try:
                with _http_client(timeout=timeout, follow_redirects=False) as transport:
                    response = transport.post(
                        base_url.rstrip("/") + "/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": model, "messages": pending, "temperature": 0,
                              "max_tokens": 600, "enable_thinking": False},
                    )
                status = response.status_code
                if status != 200:
                    failure = classify_response_error(status, response.text)
                else:
                    envelope = ProviderCompletion.model_validate_json(response.text)
                    usage = envelope.usage
                    raw = envelope.choices[0].message.content
                    if envelope.choices[0].finish_reason not in (None, "stop"):
                        raise ValueError("响应未完整结束")
                    validate(raw)
            except httpx2.TimeoutException:
                failure = LLMError("MODEL_TIMEOUT", "识别响应超时，本张照片不再重试。")
            except httpx2.RequestError:
                failure = LLMError("MODEL_NETWORK", "无法连接识别服务，请检查网络。")
            except (ValidationError, ValueError):
                failure = LLMError("MODEL_RESPONSE", "识别输出未通过JSON/单品字段校验，请返回完整且合法的字段。")
            finally:
                _log(context, started, usage, failure.category.value if failure else "ok", failure)
            attempt = {"http_status": status, "raw_content": raw.replace(key, "[REDACTED]") if raw else raw,
                       "latency_ms": round((perf_counter() - started) * 1000),
                       "error": str(failure) if failure else None,
                       "category": failure.category.value if failure else None}
            attempts.append(attempt)
            if failure is None or failure.category in (ErrorCategory.AUTH, ErrorCategory.TIMEOUT):
                break
            if retry == max_retries:
                break
            if failure.category == ErrorCategory.RATE_LIMIT:
                if context.rate_retries >= 1:
                    break
                context.rate_retries += 1
                wait(retry_delay)
            pending.append({"role": "user", "content": f"上次识别失败：{failure} 请按原始要求重新识别。"})
    return {**attempts[-1], "attempts": attempts, "latency_ms": round((perf_counter() - total_started) * 1000)}
