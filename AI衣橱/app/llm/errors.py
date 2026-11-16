from pydantic import ValidationError

from app.models import ErrorCategory, ProviderErrorEnvelope, Shortage

PUBLIC_MESSAGES = {
    ErrorCategory.AUTH: "AI 服务暂不可用，请稍后再试",
    ErrorCategory.RATE_LIMIT: "AI 正忙，已为你用基础规则搭配",
    ErrorCategory.TIMEOUT: "AI 响应超时，已为你用基础规则搭配",
    ErrorCategory.PARSE: "AI 输出暂不可用，请稍后再试",
    ErrorCategory.NETWORK: "AI 服务暂不可用，请稍后再试",
}


class LLMError(Exception):
    def __init__(
        self, code: str, message: str, *, category: ErrorCategory | None = None,
        http_status: int | None = None, provider_code: str | None = None,
        diagnostic: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.category = category or {
            "MODEL_CONFIG": ErrorCategory.AUTH,
            "MODEL_TIMEOUT": ErrorCategory.TIMEOUT,
            "MODEL_RESPONSE": ErrorCategory.PARSE,
        }.get(code, ErrorCategory.NETWORK)
        self.http_status = http_status
        self.provider_code = provider_code
        self.diagnostic = diagnostic


def classify_response_error(status: int, body: str) -> LLMError:
    try:
        provider_code = ProviderErrorEnvelope.model_validate_json(body).error.code
    except ValidationError:
        provider_code = None
    # 只记录已核实的提供方枚举，避免错误体反射任意敏感文本。
    if provider_code not in {"limit_requests", "AccessDenied.Unpurchased"}:
        provider_code = None
    if status in (401, 403):
        diagnostic = "invalid_key" if status == 401 else (
            "model_unpurchased" if provider_code == "AccessDenied.Unpurchased" else "access_denied"
        )
        return LLMError(
            "MODEL_CONFIG", f"AI 服务未授权，请检查配置（HTTP {status}）。",
            category=ErrorCategory.AUTH, http_status=status,
            provider_code=provider_code, diagnostic=diagnostic,
        )
    if status == 429:
        return LLMError(
            "MODEL_NETWORK", "模型服务返回 HTTP 429，请等待后重试。",
            category=ErrorCategory.RATE_LIMIT, http_status=status, provider_code=provider_code,
        )
    return LLMError("MODEL_NETWORK", f"模型服务返回 HTTP {status}，请稍后再试。", http_status=status)


class ServiceError(Exception):
    def __init__(self, status: int, *, shortage: Shortage | None = None):
        self.status = status
        self.shortage = shortage
        self.message = {
            400: "请求参数无效，请检查后重试。",
            422: "衣柜没有符合条件的完整搭配，请补充缺少的单品。",
            504: "AI 响应超时，请稍后再试。",
        }.get(status, "服务暂时不可用，请稍后重试。")
        super().__init__(self.message)


class FallbackValidationError(ServiceError):
    def __init__(self, errors: list[str]):
        super().__init__(500)
        self.errors = errors


def public_model_failure(category: ErrorCategory | None) -> tuple[int, str]:
    status = {ErrorCategory.AUTH: 503, ErrorCategory.RATE_LIMIT: 429, ErrorCategory.TIMEOUT: 504}.get(category, 500)
    # 这些异常响应没有基础方案，不能声称已经生成了降级产物。
    message = {
        ErrorCategory.RATE_LIMIT: "AI 正忙，请稍后再试。",
        ErrorCategory.TIMEOUT: "AI 响应超时，请稍后再试。",
    }.get(category, PUBLIC_MESSAGES.get(category, "服务暂时不可用，请稍后重试。"))
    return status, message
