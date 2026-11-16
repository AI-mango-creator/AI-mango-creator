import json
import re
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import connect_db, init_db
from app.main import app
from app.models import WardrobeItem, derive_needs_confirm
from app.routers.wardrobe import database_path
from app.services.filter import filter_candidates
from scripts.claim_legacy import claim_legacy
from scripts.seed import seed_database


def test_delete_item_removes_references_empty_sets_and_last_photo(client, database):
    items = client.get("/api/wardrobe/items").json()
    target, remaining = items[:2]
    image = database.parent / "uploads" / OWNER / "shared.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"photo")
    with closing(connect_db(database)) as connection, connection:
        connection.execute("UPDATE wardrobe_items SET image_path=? WHERE id IN (?,?)",
                           (f"uploads/{OWNER}/shared.jpg", target["id"], remaining["id"]))
        connection.execute("INSERT INTO sessions(id,temp_c,occasion,formality_target,excluded_items,status,latency_ms,"
                           "prompt_version,sources,owner_id) VALUES('delete-session',18,'commute','[1,5]','[]','ok',1,'test','{}',?)",
                           (OWNER,))
        for set_id, rank in [("empty-after-delete", 1), ("still-has-item", 2)]:
            connection.execute("INSERT INTO outfit_sets(id,session_id,rank,reason,degraded,sources,owner_id) "
                               "VALUES(?,'delete-session',?,'颜色可核对',0,'{}',?)", (set_id, rank, OWNER))
            connection.execute("INSERT INTO outfit_items(set_id,item_id,slot,sources,owner_id) VALUES(?,?,'top','{}',?)",
                               (set_id, target["id"], OWNER))
        connection.execute("INSERT INTO outfit_items(set_id,item_id,slot,sources,owner_id) "
                           "VALUES('still-has-item',?,'bottom','{}',?)", (remaining["id"], OWNER))
    response = client.delete(f"/api/wardrobe/items/{target['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert image.exists()  # 共用照片的另一件仍在。
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM outfit_items WHERE item_id=?", (target["id"],)).fetchone()[0] == 0
        assert [row[0] for row in connection.execute("SELECT id FROM outfit_sets")] == ["still-has-item"]
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    assert client.delete(f"/api/wardrobe/items/{target['id']}").status_code == 404
    assert client.delete(f"/api/wardrobe/items/{remaining['id']}").status_code == 204
    assert not image.exists()
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM outfit_sets").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE - 2


def test_delete_cross_owner_and_missing_are_both_404(client, database):
    item = client.get("/api/wardrobe/items").json()[0]
    other = "22222222-2222-4222-8222-222222222222"
    denied = client.delete(f"/api/wardrobe/items/{item['id']}", headers={"X-Device-ID": other})
    absent = client.delete("/api/wardrobe/items/missing", headers={"X-Device-ID": other})
    assert denied.status_code == absent.status_code == 404
    assert denied.json() == absent.json()
    assert len(client.get("/api/wardrobe/items").json()) == WARDROBE_SIZE


def test_delete_file_failure_rolls_back_database(client, database, monkeypatch):
    item = client.get("/api/wardrobe/items").json()[0]
    image = database.parent / "uploads" / OWNER / "failure.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"photo")
    with closing(connect_db(database)) as connection, connection:
        connection.execute("UPDATE wardrobe_items SET image_path=? WHERE id=?", (f"uploads/{OWNER}/failure.jpg", item["id"]))
    original_unlink = Path.unlink

    def cannot_unlink(self, *args, **kwargs):
        if self == image:
            raise PermissionError("private-filesystem-error")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", cannot_unlink)
    response = client.delete(f"/api/wardrobe/items/{item['id']}")
    assert response.status_code == 500
    assert "重试" in response.json()["detail"]
    assert "private-filesystem-error" not in response.text
    assert image.exists()
    assert any(row["id"] == item["id"] for row in client.get("/api/wardrobe/items").json())


def test_delete_cannot_remove_another_owners_photo(client, database):
    item = client.get("/api/wardrobe/items").json()[0]
    image = database.parent / "uploads" / "another-owner" / "protected.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"protected")
    with closing(connect_db(database)) as connection, connection:
        connection.execute("UPDATE wardrobe_items SET image_path=? WHERE id=?", ("uploads/another-owner/protected.jpg", item["id"]))
    response = client.delete(f"/api/wardrobe/items/{item['id']}")
    assert response.status_code == 500
    assert image.read_bytes() == b"protected"
    assert any(row["id"] == item["id"] for row in client.get("/api/wardrobe/items").json())

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = PROJECT_ROOT / "cases" / "cases.json"

# 衣柜规模唯一来源是 cases.json，测试不得写死件数。
WARDROBE_SIZE = len(json.loads(CASES_PATH.read_text(encoding="utf-8"))["wardrobe"])
OWNER = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "wardrobe.db"
    init_db(path)
    seed_database(path)
    claim_legacy(path, device_id=OWNER, apply=True)
    return path


@pytest.fixture
def client(database):
    app.dependency_overrides[database_path] = lambda: database
    try:
        with TestClient(app, headers={"X-Device-ID": OWNER}) as client:
            yield client
    finally:
        app.dependency_overrides.pop(database_path, None)


def test_get_all_items_matching_models_and_sources(client):
    response = client.get("/api/wardrobe/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == WARDROBE_SIZE
    for item in items:
        assert set(item) == set(WardrobeItem.model_fields)
        assert item == WardrobeItem.model_validate(item).model_dump(mode="json")
        assert item["sources"]["category"] == "model"
        assert item["sources"]["confidence"] == "model"


def test_get_empty_database(client, database):
    # 测试夹具是独立临时库；删除测试数据不涉及真实衣柜。
    with closing(connect_db(database)) as connection, connection:
        connection.execute("DELETE FROM wardrobe_items")
    assert client.get("/api/wardrobe/items").json() == []


def test_patch_only_given_fields_persists_and_marks_sources(client, database):
    before = client.get("/api/wardrobe/items").json()[0]
    patch = {"sub": "白衬衫", "colors": ["白色", "蓝色"], "material": "棉", "pattern": "条纹", "category": "top"}
    response = client.patch(f"/api/wardrobe/items/{before['id']}", json=patch)
    assert response.status_code == 200
    updated = response.json()
    assert updated["user_edited"] is True
    assert updated["needs_confirm"] is False
    for name, value in patch.items():
        assert updated[name] == value
        assert updated["sources"][name] == "user"
    for name in ("id", "created_at", "confidence", "warmth", "formality", "seasons", "image_path", "name"):
        assert updated[name] == before[name]
        assert updated["sources"][name] == before["sources"][name]
    with closing(connect_db(database)) as connection:
        row = connection.execute("SELECT * FROM wardrobe_items WHERE id=?", (before["id"],)).fetchone()
        assert json.loads(row["colors"]) == patch["colors"]
        assert json.loads(row["sources"])["sub"] == "user"
    assert next(item for item in client.get("/api/wardrobe/items").json() if item["id"] == before["id"]) == updated


@pytest.mark.parametrize("body", [
    {}, {"warmth": 9}, {"warmth": 2}, {"formality": 4}, {"seasons": ["summer"]},
    {"confidence": 1}, {"id": "other"}, {"sources": {"confidence": "user"}},
    {"user_edited": True}, {"needs_confirm": False}, {"name": "新名称"},
    {"category": "invalid"}, {"category": None}, {"colors": "白色"},
    {"sub": "不得部分写入", "warmth": 4}, [], None,
])
def test_patch_invalid_body_rejected_without_partial_write(client, body):
    before = client.get("/api/wardrobe/items").json()
    response = client.patch("/api/wardrobe/items/W01", json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert any("\u4e00" <= char <= "\u9fff" for char in response.json()["detail"])
    assert "Traceback" not in response.text
    assert client.get("/api/wardrobe/items").json() == before


def test_patch_missing_item_is_404(client):
    response = client.patch("/api/wardrobe/items/W99", json={"sub": "x"})
    assert response.status_code == 404
    assert "单品" in response.json()["detail"]
    assert "Traceback" not in response.text


def test_low_confidence_item_reenters_filter_after_patch(client, database):
    with closing(connect_db(database)) as connection, connection:
        connection.execute("UPDATE wardrobe_items SET confidence=0.4, needs_confirm=1 WHERE id='W01'")
    items = [WardrobeItem.model_validate(item) for item in client.get("/api/wardrobe/items").json()]
    assert next(item for item in items if item.id == "W01").needs_confirm is True
    before = filter_candidates(items, temp_c=18, occasion="commute")
    assert "W01" not in {item.id for item in before["candidates"]}
    response = client.patch("/api/wardrobe/items/W01", json={"sub": "修正后的衬衫"})
    assert response.status_code == 200
    assert response.json()["confidence"] == 0.4
    assert response.json()["needs_confirm"] is False
    items = [WardrobeItem.model_validate(item) for item in client.get("/api/wardrobe/items").json()]
    after = filter_candidates(items, temp_c=18, occasion="commute")
    assert "W01" in {item.id for item in after["candidates"]}


@pytest.mark.parametrize(("confidence", "edited", "expected"), [
    (None, False, True), (0.4, False, True), (0.599, False, True),
    (0.6, False, True), (0.7, False, True), (1.0, False, True),
    (None, True, False), (0.4, True, False),
])
def test_single_confirmation_rule(confidence, edited, expected):
    # D10-b明确替代阈值；保留原8个输入，更新0.6/0.7/1.0的业务期望。
    assert derive_needs_confirm(uploaded=True, user_edited=edited) is expected
    assert WardrobeItem(id="aux", confidence=confidence).confidence == confidence


@pytest.mark.parametrize("edited", [False, True])
def test_non_uploaded_seed_does_not_enter_confirmation_queue(edited):
    assert derive_needs_confirm(uploaded=False, user_edited=edited) is False


def test_malformed_json_is_readable(client):
    response = client.patch("/api/wardrobe/items/W01", content="{", headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert "JSON" in response.json()["detail"]


def test_database_failure_is_readable(client, database):
    app.dependency_overrides[database_path] = lambda: Path(database) / "invalid.db"
    with TestClient(app, headers={"X-Device-ID": OWNER}, raise_server_exceptions=False) as safe_client:
        response = safe_client.get("/api/wardrobe/items")
    assert response.status_code == 500
    assert "服务" in response.json()["detail"]
    assert "Traceback" not in response.text


@pytest.fixture
def recognition(monkeypatch, tmp_path):
    import httpx2

    from app.llm import client as llm

    record = json.loads((PROJECT_ROOT / "docs/reports/raw/recognition/R01.json").read_text())
    item = record["parsed"]["items"][0] | {"warmth": 1, "confidence": 0.4, "seasons": ["spring", "winter"]}
    calls = []
    script = [{"items": [item]}]
    rate_body, forbidden_body = re.findall(r"```json\n(.*?)\n```", (PROJECT_ROOT / "docs/reports/api-error-samples.md").read_text(), re.DOTALL)
    def transport(request):
        calls.append(json.loads(request.content))
        value = script.pop(0) if len(script) > 1 else script[0]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, int):
            return httpx2.Response(value, text={429: rate_body, 403: forbidden_body}.get(value, ""))
        raw = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value
        return httpx2.Response(200, json={"choices": [{"message": {"content": raw}}]})

    real = httpx2.Client
    monkeypatch.setattr(llm, "_configuration", lambda: ("test-secret", "https://example.invalid/v1", "text-model"))
    monkeypatch.setattr(llm, "_http_client", lambda **kwargs: real(transport=httpx2.MockTransport(transport), **kwargs))
    monkeypatch.setattr(llm, "LOG_PATH", tmp_path / "llm.log")
    return calls, script


def upload(client, draft_id, data=None):
    photo = (PROJECT_ROOT / "cases/images/cloth01.jpg").read_bytes() if data is None else data
    return client.post("/api/wardrobe/items", data={"draft_id": str(draft_id)},
                       files={"photo": ("photo.jpg", photo, "image/jpeg")})


def test_upload_persists_corrections_sources_photo_and_confirmation(client, database, recognition):
    calls, _ = recognition
    draft_id = uuid4()
    response = upload(client, draft_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["draft_id"] == str(draft_id) and body["reused"] is False
    assert body["prompt_version"] == "item_extract.v2" and body["latency_ms"] >= 0
    item = body["items"][0]
    assert item["warmth"] == 2 and item["seasons"] == ["spring", "winter"]
    assert item["confidence"] == 0.4 and item["needs_confirm"] is True
    assert item["sources"]["warmth"] == "derived"
    assert item["sources"]["seasons"] == "model"
    assert item["sources"]["confidence"] == "model"
    assert item["sources"]["_corrections"]["source"] == "derived"
    assert item["sources"]["_corrections"]["entries"] == ["warmth: 1 -> 2（outer 类目下限）"]
    assert body["corrections"] == ["items[0].warmth: 1 -> 2（outer 类目下限）"]
    with closing(connect_db(database)) as connection:
        row = connection.execute("SELECT * FROM wardrobe_items WHERE id=?", (item["id"],)).fetchone()
        assert json.loads(row["sources"]) == item["sources"]
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE + 1
    assert (database.parent / item["image_path"]).is_file()
    photo = client.get(f"/api/wardrobe/items/{item['id']}/photo")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert photo.content == (PROJECT_ROOT / "cases/images/cloth01.jpg").read_bytes()
    assert calls[0]["model"] == "qwen3.8-omni-flash"
    assert "sub 必须给具体款型名" in calls[0]["messages"][0]["content"][0]["text"]
    updated = client.patch(f"/api/wardrobe/items/{item['id']}", json={"sub": "修正款型"}).json()
    assert updated["needs_confirm"] is False and updated["user_edited"] is True
    assert updated["sources"]["_corrections"] == item["sources"]["_corrections"]


def test_upload_retries_are_idempotent_and_reject_changed_photo(client, database, recognition):
    calls, _ = recognition
    draft = uuid4()
    first = upload(client, draft).json()
    second = upload(client, draft)
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["items"] == first["items"]
    assert len(calls) == 1
    conflict = upload(client, draft, (PROJECT_ROOT / "cases/images/cloth02.jpg").read_bytes())
    assert conflict.status_code == 409 and "图片" in conflict.json()["detail"]
    assert len(calls) == 1
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE + 1


def test_upload_conflicting_seasons_are_derived_and_persisted(client, database, recognition):
    _, script = recognition
    script[0]["items"][0].update(category="top", warmth=1, seasons=["spring", "summer"])
    response = upload(client, uuid4())
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["seasons"] == ["summer"]
    assert item["sources"]["seasons"] == "derived" and item["sources"]["warmth"] == "model"
    assert item["sources"]["_corrections"]["entries"] == ["seasons: ['spring', 'summer'] -> ['summer']（filter_spec 一致性）"]
    with closing(connect_db(database)) as connection:
        row = connection.execute("SELECT sources FROM wardrobe_items WHERE id=?", (item["id"],)).fetchone()
        assert json.loads(row["sources"]) == item["sources"]


def test_timeout_then_explicit_retry_uses_same_draft_without_duplicate(client, database, recognition):
    import httpx2

    calls, script = recognition
    script.insert(0, httpx2.ReadTimeout("injected"))
    draft = uuid4()
    failed = upload(client, draft)
    assert failed.status_code == 504
    assert failed.json()["category"] == "timeout"
    assert "请重试，或稍后再试" in failed.json()["detail"]
    assert "手动建档" not in failed.json()["detail"]
    assert len(calls) == 1
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE
    assert not list((database.parent / "uploads").rglob("*.jpg"))
    assert upload(client, draft).status_code == 201
    assert upload(client, draft).status_code == 200
    assert len(calls) == 2
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE + 1


@pytest.mark.parametrize(("scripted", "status", "category", "count"), [
    (401, 503, "auth", 1), (403, 503, "auth", 1), ("not JSON", 500, "parse", 3),
])
def test_upload_model_errors_are_readable_and_do_not_insert(client, database, recognition, scripted, status, category, count):
    calls, script = recognition
    script[:] = [scripted]
    response = upload(client, uuid4())
    assert response.status_code == status
    assert response.json()["category"] == category
    assert "Traceback" not in response.text and "test-secret" not in response.text
    assert len(calls) == count
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE


def test_upload_non_clothing_rejected_without_row_or_photo(client, database, recognition):
    calls, script = recognition
    script[:] = [{"items": []}]
    response = upload(client, uuid4())
    assert response.status_code == 422 and response.json()["code"] == "NOT_CLOTHING"
    assert "没有识别到衣物" in response.json()["detail"] and len(calls) == 1
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE
    assert not list((database.parent / "uploads").rglob("*.jpg"))


def test_upload_parameter_errors_are_for_upload_not_patch(client, recognition):
    response = client.post("/api/wardrobe/items", data={"draft_id": "invalid"})
    assert response.status_code == 422
    assert "上传" in response.json()["detail"] and "只允许修改" not in response.json()["detail"]
    response = upload(client, uuid4(), b"not an image")
    assert response.status_code == 422 and not recognition[0]


def test_upload_rate_limit_uses_real_fixture_and_injected_wait(client, database, recognition, monkeypatch):
    from functools import partial

    from app.llm import client as llm

    calls, script = recognition
    script[:] = [429]
    waits = []
    monkeypatch.setattr(llm, "vision", partial(llm.vision, wait=waits.append))
    response = upload(client, uuid4())
    assert response.status_code == 429 and response.json()["category"] == "rate_limit"
    assert len(calls) == 2 and waits == [5]
    assert "429" in calls[1]["messages"][-1]["content"]
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE


def test_upload_network_failures_keep_category_without_traceback(client, database, recognition):
    import httpx2

    calls, script = recognition
    script[:] = [httpx2.ConnectError("private-internal")]
    response = upload(client, uuid4())
    assert response.status_code == 500 and response.json()["category"] == "network"
    assert len(calls) == 3
    assert "private-internal" not in response.text and "Traceback" not in response.text
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE


def test_same_draft_concurrent_uploads_call_model_once(client, database, recognition):
    from concurrent.futures import ThreadPoolExecutor

    draft = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(client, draft), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json()["items"] == responses[1].json()["items"]
    assert len(recognition[0]) == 1
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE + 1


def test_high_confidence_upload_always_waits_then_explicit_confirmation_preserves_model_sources(client, database, recognition):
    _, script = recognition
    script[0]["items"][0].update(category="top", confidence=0.95, warmth=1, seasons=["summer"])
    item = upload(client, uuid4()).json()["items"][0]
    assert item["needs_confirm"] is True
    assert item["confidence"] == 0.95 and item["sources"]["confidence"] == "model"
    before = filter_candidates([WardrobeItem.model_validate(item)], temp_c=28, occasion="weekend")
    assert item["id"] not in {x.id for x in before["candidates"]}
    confirmed = client.post(f"/api/wardrobe/items/{item['id']}/confirm")
    assert confirmed.status_code == 200
    result = confirmed.json()
    assert result["needs_confirm"] is False and result["user_edited"] is True
    for name in ("confidence", "category", "sub", "warmth", "seasons"):
        assert result[name] == item[name]
        assert result["sources"][name] == item["sources"][name]
    assert client.post(f"/api/wardrobe/items/{item['id']}/confirm").json() == result
    after = filter_candidates([WardrobeItem.model_validate(result)], temp_c=28, occasion="weekend")
    assert item["id"] in {x.id for x in after["candidates"]}
    with closing(connect_db(database)) as connection:
        row = connection.execute("SELECT * FROM wardrobe_items WHERE id=? AND owner_id=?", (item["id"], OWNER)).fetchone()
        assert row["needs_confirm"] == 0 and row["confidence"] == 0.95


def test_confirmation_cannot_access_other_owner_and_rejects_attribute_payload(client, recognition):
    item = upload(client, uuid4()).json()["items"][0]
    path = f"/api/wardrobe/items/{item['id']}/confirm"
    assert client.post(path, headers={"X-Device-ID": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}).status_code == 404
    assert client.post(path, json={"confidence": 1}).status_code == 422
    assert client.post("/api/wardrobe/items/absent/confirm").status_code == 404


def test_confirmation_migration_marks_only_unedited_uploads(database):
    from app.db import to_db_values
    from app.models import UploadAudit
    audit = UploadAudit(draft_id=uuid4(), photo_sha256="a" * 64)
    with closing(connect_db(database)) as c, c:
        for item_id, edited in (("old-upload", False), ("old-confirmed", True)):
            item = WardrobeItem(id=item_id, owner_id=OWNER, confidence=0.99, needs_confirm=False,
                                user_edited=edited, sources={"_upload": audit})
            values = to_db_values(item)
            c.execute(f"INSERT INTO wardrobe_items ({', '.join(values)}) VALUES ({', '.join(':'+k for k in values)})", values)
        c.execute("PRAGMA user_version=2")
    init_db(database)
    init_db(database)
    with closing(connect_db(database)) as c:
        assert c.execute("SELECT needs_confirm FROM wardrobe_items WHERE id='old-upload'").fetchone()[0] == 1
        assert c.execute("SELECT needs_confirm FROM wardrobe_items WHERE id='old-confirmed'").fetchone()[0] == 0
        assert c.execute("SELECT needs_confirm FROM wardrobe_items WHERE id='W01'").fetchone()[0] == 0
