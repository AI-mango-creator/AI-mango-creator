import json
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, Response

from app.db import (
    DB_PATH,
    connect_db,
    expire_quotas,
    init_db,
    owner_lock,
    reserve_quota,
    to_db_values,
)
from app.models import (
    CorrectionAudit,
    UploadAudit,
    WardrobeItem,
    WardrobePatch,
    WardrobeUploadResponse,
)
from app.services.extract import extract_photo

router = APIRouter(prefix="/api/wardrobe", tags=["衣柜"])


def database_path() -> Path:
    init_db(DB_PATH)
    return DB_PATH


Database = Annotated[Path, Depends(database_path)]
def request_owner(request: Request, path: Database) -> str:
    owner = request.state.owner_id
    request.app.state.quota_paths.add(path)
    expire_quotas(path)
    return owner


Owner = Annotated[str, Depends(request_owner)]
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _item(row) -> WardrobeItem:
    values = dict(row)
    for field in ("colors", "seasons", "sources"):
        values[field] = json.loads(values[field])
    return WardrobeItem.model_validate(values)


@router.get("/items", response_model=list[WardrobeItem])
def list_items(path: Database, owner_id: Owner):
    with closing(connect_db(path)) as connection:
        return [_item(row) for row in connection.execute("SELECT * FROM wardrobe_items WHERE owner_id=? ORDER BY id", (owner_id,))]


def _photo_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise HTTPException(422, "上传内容不是支持的图片，请选择JPG、PNG或WebP照片。")


def _upload_response(draft_id, items, started, reused):
    corrections = [f"items[{index}].{entry}" for index, item in enumerate(items)
                   if isinstance(item.sources.get("_corrections"), CorrectionAudit)
                   for entry in item.sources["_corrections"].entries]
    return WardrobeUploadResponse(draft_id=draft_id, items=items, corrections=corrections,
                                  latency_ms=round((perf_counter() - started) * 1000), reused=reused,
                                  prompt_version=items[0].sources['_upload'].prompt_version if items else 'item_extract.v3')


@router.post("/items", response_model=WardrobeUploadResponse, status_code=201)
def upload_item(request: Request, path: Database, photo: Annotated[UploadFile, File()],
                draft_id: Annotated[UUID, Form()], owner_id: Owner):
    started = getattr(request.state, "upload_started", perf_counter())
    data = photo.file.read(MAX_PHOTO_BYTES + 1)
    if not data:
        raise HTTPException(422, "上传照片为空，请重新选择图片。")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "照片超过10MB，请换一张较小的图片。")
    mime_type, extension = _photo_type(data)
    digest, prefix = sha256(data).hexdigest(), f"I{uuid4().hex}-"
    directory = path.parent / "uploads" / owner_id
    with owner_lock(path, owner_id):
        with closing(connect_db(path)) as connection:
            rows = connection.execute("SELECT * FROM wardrobe_items WHERE owner_id=? "
                                      "AND json_extract(sources, '$._upload.draft_id')=? ORDER BY id",
                                      (owner_id, str(draft_id))).fetchall()
        if rows:
            items = [_item(row) for row in rows]
            audit = items[0].sources.get("_upload")
            if not isinstance(audit, UploadAudit) or audit.photo_sha256 != digest:
                raise HTTPException(409, "同一上传ID对应的图片不同，请重新选择图片。")
            response = _upload_response(draft_id, items, started, True)
            return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
        directory.mkdir(parents=True, exist_ok=True)
        image = directory / f"{draft_id.hex}{extension}"
        try:
            image.write_bytes(data)
            reserve_quota(path, owner_id, "recognition")
            items = extract_photo(image, image_reference=f"uploads/{owner_id}/{image.name}", mime_type=mime_type,
                                  request_id=f"upload:{draft_id}")
            for index, item in enumerate(items):
                values = item.model_dump()
                values["id"] = f"{prefix}{index:02}"
                values["owner_id"] = owner_id
                values["sources"]["_upload"] = UploadAudit(draft_id=draft_id, photo_sha256=digest,
                                                           prompt_version='item_extract.v3')
                items[index] = WardrobeItem.model_validate(values)
            with closing(connect_db(path)) as connection, connection:
                for item in items:
                    values = to_db_values(item)
                    names = ", ".join(values)
                    parameters = ", ".join(f":{field}" for field in values)
                    connection.execute(f"INSERT INTO wardrobe_items ({names}) VALUES ({parameters})", values)
        except Exception:
            image.unlink(missing_ok=True)
            raise
        return _upload_response(draft_id, items, started, False)


@router.get("/items/{item_id}/photo")
def item_photo(item_id: str, path: Database, owner_id: Owner):
    with closing(connect_db(path)) as connection:
        row = connection.execute("SELECT * FROM wardrobe_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
    if row is None or not row["image_path"]:
        raise HTTPException(404, "这件单品尚无照片。")
    image = (path.parent / row["image_path"]).resolve()
    if not image.is_relative_to((path.parent / "uploads").resolve()) or not image.is_file():
        raise HTTPException(404, "照片暂时无法读取，请重新上传。")
    return FileResponse(image)


@router.patch("/items/{item_id}", response_model=WardrobeItem)
def patch_item(item_id: str, patch: WardrobePatch, path: Database, owner_id: Owner):
    return _confirm_or_patch(path, owner_id, item_id, patch)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, path: Database, owner_id: Owner):
    with owner_lock(path, owner_id), closing(connect_db(path)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT image_path FROM wardrobe_items WHERE id=? AND owner_id=?",
                                 (item_id, owner_id)).fetchone()
        if row is None:
            raise HTTPException(404, "这件单品不存在，请重新加载衣柜。")
        image = None
        if row["image_path"]:
            image = (path.parent / row["image_path"]).resolve()
            if not image.is_relative_to((path.parent / "uploads" / owner_id).resolve()):
                raise HTTPException(500, "照片清理未完成，请稍后重试。")
            shared = connection.execute("SELECT 1 FROM wardrobe_items WHERE owner_id=? AND image_path=? AND id<>? LIMIT 1",
                                        (owner_id, row["image_path"], item_id)).fetchone()
            if shared:
                image = None
        connection.execute("DELETE FROM outfit_items WHERE owner_id=? AND item_id=?", (owner_id, item_id))
        connection.execute("DELETE FROM outfit_sets WHERE owner_id=? AND NOT EXISTS "
                           "(SELECT 1 FROM outfit_items WHERE set_id=outfit_sets.id AND owner_id=?)", (owner_id, owner_id))
        connection.execute("DELETE FROM wardrobe_items WHERE owner_id=? AND id=?", (owner_id, item_id))
        if image is not None:
            try:
                image.unlink(missing_ok=True)
            except OSError:
                raise HTTPException(500, "照片清理未完成，删除未保存，请稍后重试。") from None
    return Response(status_code=204)


@router.post("/items/{item_id}/confirm", response_model=WardrobeItem)
def confirm_item(item_id: str, path: Database, owner_id: Owner, body: None = Body(default=None)):
    return _confirm_or_patch(path, owner_id, item_id, None)


def _confirm_or_patch(path, owner_id, item_id, patch):
    with owner_lock(path, owner_id), closing(connect_db(path)) as connection, connection:
        # 读取、合并来源及更新在同一写事务内，避免并发覆盖其他编辑来源。
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM wardrobe_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="这件单品不存在，请重新加载衣柜。")
        item = _item(row)
        if item.wardrobe_group == 'unclassified' and (patch is None or not {'category', 'wardrobe_group'} & patch.model_fields_set):
            raise HTTPException(422, '请先选择分类并填写具体品类名称，再确认这件单品。')
        if item.wardrobe_group == 'unclassified' and not (patch.sub and patch.sub.strip()):
            raise HTTPException(422, '请填写具体品类名称，再确认这件单品。')
        updated = item.apply_user_patch(patch) if patch is not None else item.confirm_recognition()
        values = to_db_values(updated)
        fields = list(dict.fromkeys([*(patch.model_fields_set if patch is not None else ()),
                                    'category', 'wardrobe_group', "user_edited", "needs_confirm", "sources"]))
        assignments = ", ".join(f"{name}=:{name}" for name in fields)
        connection.execute(f"UPDATE wardrobe_items SET {assignments} WHERE id=:id AND owner_id=:owner_id", values)
        return updated


@router.delete("/items")
def clear_items(path: Database, owner_id: Owner) -> dict[str, int]:
    from app.services import community, personal, tryon

    personal.recover_pending_clear(path, owner_id)
    with owner_lock(path, owner_id):
        operation = personal.prepare_clear(path, owner_id)
        try:
            with closing(connect_db(path)) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                personal.stage_private(path, owner_id, operation)
                photos = connection.execute("SELECT count(DISTINCT image_path) FROM wardrobe_items WHERE owner_id=?", (owner_id,)).fetchone()[0]
                personal.clear_records(connection, path, owner_id)
                community.clear_for_owner(connection, owner_id)
                tryon.clear_for_owner(connection, owner_id)
                counts = {}
                for table in ("outfit_items", "outfit_sets", "sessions", "wardrobe_items"):
                    counts[table] = connection.execute(f"DELETE FROM {table} WHERE owner_id=?", (owner_id,)).rowcount
                connection.execute("DELETE FROM body_profiles WHERE owner_id=?", (owner_id,))
                connection.execute("UPDATE personal_write_receipts SET state='consumed' WHERE token_hash=?", (operation,))
                counts["photos"] = photos
        except Exception:
            personal.finish_clear(path, operation, False)
            raise
        try:
            personal.finish_clear(path, operation, True)
            community.purge_trash(path, owner_id)
        except OSError:
            raise HTTPException(500, "数据已清空，照片清理未完成，请重试。") from None
    return counts
