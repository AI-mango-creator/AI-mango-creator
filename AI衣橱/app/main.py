import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from time import perf_counter
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.db import _quota_day, expire_quotas
from app.llm.errors import LLMError, ServiceError, public_model_failure
from app.models import ExtractionFailureResponse
from app.routers.community import router as community_router
from app.routers.ootd import router as ootd_router
from app.routers.outfits import router as outfits_router
from app.routers.personal import router as personal_router
from app.routers.profile import router as profile_router
from app.routers.tryon import router as tryon_router
from app.routers.wardrobe import database_path
from app.routers.wardrobe import router as wardrobe_router
from app.routers.weather import router as weather_router
from app.services.compose import ComposeError
from app.services.extract import ExtractError

logger = logging.getLogger(__name__)


async def _expire_at_midnight(application):
    while True:
        now, _, midnight = _quota_day()
        await asyncio.sleep(max(0.01, (midnight - now).total_seconds()))
        for path in tuple(application.state.quota_paths):
            try:
                await asyncio.to_thread(expire_quotas, path)
            except (OSError, sqlite3.Error):
                logger.error("额度过期清理未完成，将在下次请求重试。")


@asynccontextmanager
async def lifespan(application):
    application.state.quota_paths = set()
    try:
        provider = application.dependency_overrides.get(database_path, database_path)
        path = provider()
        from app.services.personal import recover_pending_clear
        recover_pending_clear(path)
        expire_quotas(path)
        application.state.quota_paths.add(path)
    except (OSError, sqlite3.Error):
        logger.error("数据库启动检查未完成，业务请求将返回中文错误。")
    task = asyncio.create_task(_expire_at_midnight(application))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="算法衣橱", lifespan=lifespan)
app.include_router(wardrobe_router)
app.include_router(outfits_router)
app.include_router(profile_router)
app.include_router(personal_router)
app.include_router(ootd_router)
app.include_router(weather_router)
app.include_router(community_router)
app.include_router(tryon_router)


@app.middleware("http")
async def upload_clock(request: Request, call_next):
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        vary = [value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()]
        if "x-device-id" not in {value.lower() for value in vary}:
            vary.append("X-Device-ID")
        response.headers["Vary"] = ", ".join(vary)
        return response

    if request.url.path.startswith("/api/"):
        try:
            ids = request.headers.getlist("X-Device-ID")
            if len(ids) != 1:
                raise ValueError("设备ID必须唯一。")
            request.state.owner_id = str(UUID(ids[0]))
        except (ValueError, TypeError, AttributeError):
            return private_response(JSONResponse(status_code=400, content={"detail": "设备标识无效，请重新打开应用后重试。"}))
    if request.method == "POST" and request.url.path == "/api/wardrobe/items":
        request.state.upload_started = perf_counter()
    response = await call_next(request)
    return private_response(response) if request.url.path.startswith("/api/") else response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    messages = {
        404: "请求的接口不存在。",
        405: "请求方式不支持。",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": (
            exc.detail if request.url.path.startswith("/api/")
            and isinstance(exc.detail, str) and any("\u4e00" <= char <= "\u9fff" for char in exc.detail)
            else messages.get(exc.status_code, "请求失败，请稍后重试。")
        )},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.method == "POST" and request.url.path == "/api/wardrobe/items":
        return JSONResponse(status_code=422, content={"detail": "上传参数无效：请选择照片并提供有效的draft_id。"})
    if not request.url.path.startswith("/api/wardrobe/"):
        return JSONResponse(status_code=400, content={"detail": "请求参数无效，请检查后重试。"})
    malformed = any(error["type"] == "json_invalid" for error in exc.errors())
    message = "JSON 格式无效，请检查修改内容。" if malformed else (
        "修改内容无效：只允许修改品类、子类、颜色、材质和图案；请检查字段、类型和品类枚举值，且至少修改一项。"
    )
    return JSONResponse(status_code=422, content={"detail": message})


@app.exception_handler(ServiceError)
async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
    content = {"detail": exc.message}
    if exc.status == 422:
        content["shortage_hint"] = exc.shortage.message if exc.shortage else exc.message
    if exc.shortage is not None:
        content["shortage"] = exc.shortage.model_dump(mode="json")
    return JSONResponse(status_code=exc.status, content=content)


@app.exception_handler(LLMError)
@app.exception_handler(ComposeError)
async def handle_model_error(request: Request, exc: LLMError | ComposeError) -> JSONResponse:
    status, message = public_model_failure(exc.category)
    return JSONResponse(status_code=status, content={"detail": message})


@app.exception_handler(ExtractError)
async def handle_extraction_error(request: Request, exc: ExtractError) -> JSONResponse:
    failure = ExtractionFailureResponse(detail=str(exc), category=exc.category, code=exc.code)
    return JSONResponse(status_code=exc.status, content=failure.model_dump(mode="json"))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("后端请求处理异常", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(
        status_code=500,
        content={"detail": "服务暂时不可用，请稍后重试。"},
        headers={"Cache-Control": "no-store", "Vary": "X-Device-ID"}
        if request.url.path.startswith("/api/") else None,
    )


if os.getenv("APP_SERVE_WEB") == "1":
    web_directory = Path(os.getenv("APP_WEB_DIR", Path(__file__).resolve().parents[1] / "web/dist")).resolve()
    if not (web_directory / "index.html").is_file():
        raise RuntimeError("找不到已构建网页，请先运行 cd web && npm run build。")

    @app.get("/", include_in_schema=False)
    async def shared_home():
        return FileResponse(web_directory / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/assets", StaticFiles(directory=web_directory / "assets", follow_symlink=False), name="web-assets")
