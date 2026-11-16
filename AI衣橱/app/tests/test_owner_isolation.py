"""设备隔离/配额/删除：全部tmp_path，模型响应仅在客户端层注入。"""

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx2
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db import connect_db, init_db
from app.llm import client as llm
from app.main import app
from app.routers.wardrobe import database_path
from app.services.fallback import fallback_outfits
from app.services.filter import filter_candidates
from scripts.seed import seed_database

ROOT = Path(__file__).resolve().parents[2]
A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
TABLES = ("wardrobe_items", "sessions", "outfit_sets", "outfit_items")


@pytest.fixture
def api(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    init_db(path)
    calls = []
    parsed = json.loads((ROOT / "docs/reports/raw/recognition/R01.json").read_text())["parsed"]
    parsed["items"][0].update(warmth=2, confidence=0.98)

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if isinstance(payload["messages"][0]["content"], list):
            raw = parsed
        else:
            from app.routers.wardrobe import list_items
            filtered = filter_candidates(list_items(path, A), temp_c=18, occasion="commute")
            result = fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
            raw = {"sets": [s.model_dump() for s in result.sets]}
        return httpx2.Response(200, json={"choices": [{"message": {"content": json.dumps(raw, ensure_ascii=False)}}]})

    real = httpx2.Client
    monkeypatch.setattr(llm, "_configuration", lambda: ("unit-test-key", "https://example.invalid/v1", "test-model"))
    monkeypatch.setattr(llm, "_http_client", lambda **kw: real(transport=httpx2.MockTransport(handler), **kw))
    monkeypatch.setattr(llm, "LOG_PATH", tmp_path / "llm.log")
    app.dependency_overrides[database_path] = lambda: path
    try:
        with TestClient(app, raise_server_exceptions=False) as http:
            yield http, path, calls
    finally:
        app.dependency_overrides.pop(database_path, None)


def headers(owner=A):
    return {"X-Device-ID": owner}


def upload(http, owner=A, draft=None):
    return http.post("/api/wardrobe/items", headers=headers(owner), data={"draft_id": str(draft or uuid4())},
                     files={"photo": ("cloth01.jpg", (ROOT / "cases/images/cloth01.jpg").read_bytes(), "image/jpeg")})


@pytest.mark.parametrize("owner", [None, "legacy", "not-uuid", ""])
def test_missing_or_invalid_device_is_rejected_not_global(api, owner):
    http, _, calls = api
    response = http.get("/api/wardrobe/items", headers={} if owner is None else headers(owner))
    assert response.status_code == 400
    assert "设备" in response.json()["detail"]
    assert not calls


def test_legacy_is_invisible_to_both_devices(api):
    http, path, _ = api
    seed_database(path)
    for owner in (A, B):
        assert http.get("/api/wardrobe/items", headers=headers(owner)).json() == []
        assert http.patch("/api/wardrobe/items/W01", headers=headers(owner), json={"sub": "不能改"}).status_code == 404


def test_two_owners_same_draft_items_photos_and_edits_are_isolated(api):
    http, path, calls = api
    draft = uuid4()
    first = upload(http, A, draft)
    second = upload(http, B, draft)
    assert first.status_code == second.status_code == 201
    a, b = first.json()["items"][0], second.json()["items"][0]
    assert a["id"] != b["id"] and a["image_path"] != b["image_path"]
    assert a["owner_id"] == A and b["owner_id"] == B
    for own, other, item in ((A, B, a), (B, A, b)):
        assert [i["id"] for i in http.get("/api/wardrobe/items", headers=headers(own)).json()] == [item["id"]]
        assert http.get(f"/api/wardrobe/items/{item['id']}/photo", headers=headers(own)).status_code == 200
        assert http.get(f"/api/wardrobe/items/{item['id']}/photo", headers=headers(other)).status_code == 404
        assert http.patch(f"/api/wardrobe/items/{item['id']}", headers=headers(other), json={"sub": "越权"}).status_code == 404
    assert upload(http, A, draft).json()["reused"] is True
    assert len(calls) == 2
    with closing(connect_db(path)) as c:
        assert c.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == 2


def test_recognition_20_per_device_cache_free_21st_429(api):
    http, path, calls = api
    draft = uuid4()
    assert upload(http, A, draft).status_code == 201
    for _ in range(19):
        assert upload(http).status_code == 201
    assert upload(http, A, draft).status_code == 200
    limit = upload(http)
    assert limit.status_code == 429 and "20" in limit.json()["detail"] and "明天" in limit.json()["detail"]
    print(f"recognition accepted=20; cached_retry=200; request21={limit.status_code}; model_calls={len(calls)}")
    assert len(calls) == 20
    assert upload(http, B).status_code == 201
    with closing(connect_db(path)) as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM daily_quotas")]
        assert len(rows) == 2
        assert all(len(x["owner_hash"]) == 64 for x in rows)
        assert A not in json.dumps(rows) and B not in json.dumps(rows)


def test_composition_30_and_shortage_free_with_owner_scoped_candidates(api):
    http, path, calls = api
    seed_database(path, owner_id=A)
    scenario = {"temp_c": 18, "occasion": "commute"}
    # B没有衣柜，不得借A候选；缺件不消耗编排配额。
    empty = http.post("/api/outfits", headers=headers(B), json=scenario)
    assert empty.status_code == 200 and empty.json()["shortage"] and not calls
    for _ in range(30):
        reply = http.post("/api/outfits", headers=headers(A), json=scenario)
        assert reply.status_code == 200, reply.text
        assert all(i["owner_id"] == A for s in reply.json()["sets"] for i in s["items"])
    reply = http.post("/api/outfits", headers=headers(A), json=scenario)
    assert reply.status_code == 429 and "30" in reply.json()["detail"]
    print(f"composition accepted=30; request31={reply.status_code}; B_shortage=200/free; model_calls={len(calls)}")
    assert len(calls) == 30
    with closing(connect_db(path)) as c:
        assert c.execute("SELECT count(*) FROM sessions WHERE owner_id=?", (A,)).fetchone()[0] == 30
        assert c.execute("SELECT count(*) FROM sessions WHERE owner_id=?", (B,)).fetchone()[0] == 1


def test_clear_deletes_four_tables_and_photos_but_retains_quota(api):
    http, path, _ = api
    a = upload(http).json()["items"][0]
    b = upload(http, B).json()["items"][0]
    seed_database(path, owner_id=A)
    http.post("/api/outfits", headers=headers(A), json={"temp_c": 18, "occasion": "commute"})
    assert (path.parent / a["image_path"]).is_file()
    response = http.delete("/api/wardrobe/items", headers=headers(A))
    assert response.status_code == 200
    with closing(connect_db(path)) as c:
        for table in TABLES:
            assert c.execute(f"SELECT count(*) FROM {table} WHERE owner_id=?", (A,)).fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM wardrobe_items WHERE owner_id=?", (B,)).fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM daily_quotas").fetchone()[0] == 2
    assert not (path.parent / a["image_path"]).exists()
    assert (path.parent / b["image_path"]).is_file()
    assert http.get("/api/wardrobe/items", headers=headers(A)).json() == []


def test_quota_concurrency_salt_restart_and_midnight_expiry(tmp_path):
    import subprocess
    import sys

    from app.db import quota_key, reserve_quota
    path = tmp_path / "quota.db"
    init_db(path)
    today = datetime(2026, 11, 13, 23, 59, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    def take(_):
        try:
            reserve_quota(path, A, "recognition", now=today)
            return True
        except HTTPException as error:
            assert error.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(take, range(24)))
    assert sum(results) == 20
    key = quota_key(path, A)
    assert key == quota_key(path, A) and key != quota_key(path, B)
    result = subprocess.run([sys.executable, "-c",
                             "import sys; from pathlib import Path; from app.db import quota_key; print(quota_key(Path(sys.argv[1]), sys.argv[2]))",
                             str(path), A], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0 and result.stdout.strip() == key
    assert (path.parent / ".quota_salt").stat().st_mode & 0o777 == 0o600
    reserve_quota(path, A, "recognition", now=today + timedelta(seconds=1))
    with closing(connect_db(path)) as c:
        rows = c.execute("SELECT * FROM daily_quotas").fetchall()
        assert len(rows) == 1 and rows[0]["recognition"] == 1 and rows[0]["day"] == "2026-11-14"
    print("quota concurrency: accepted=20/24; rejected=4; next_day_count=1; expired_rows=0; salt survives subprocess")


def test_failed_model_request_is_charged_once_and_clear_cannot_reset_limit(api, monkeypatch):
    http, path, _ = api
    from app.db import quota_key, reserve_quota
    def timeout(*args, **kwargs):
        raise llm.LLMError("MODEL_TIMEOUT", "注入超时")
    monkeypatch.setattr(llm, "vision", timeout)
    response = upload(http)
    assert response.status_code == 504
    with closing(connect_db(path)) as c:
        assert c.execute("SELECT recognition FROM daily_quotas WHERE owner_hash=?", (quota_key(path, A),)).fetchone()[0] == 1
    for _ in range(19):
        reserve_quota(path, A, "recognition")
    assert http.delete("/api/wardrobe/items", headers=headers()).status_code == 200
    assert upload(http).status_code == 429


def test_delete_waits_for_inflight_upload_then_removes_it(api, monkeypatch):
    from threading import Event
    http, path, _ = api
    original = llm.vision
    entered, release, deleting = Event(), Event(), Event()
    def pause_vision(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)
    monkeypatch.setattr(llm, "vision", pause_vision)
    def delete():
        deleting.set()
        return http.delete("/api/wardrobe/items", headers=headers())
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(upload, http)
        assert entered.wait(3)
        clearing = pool.submit(delete)
        assert deleting.wait(3)
        assert not clearing.done()
        release.set()
        assert pending.result().status_code == 201
        assert clearing.result().status_code == 200
    with closing(connect_db(path)) as c:
        assert c.execute("SELECT count(*) FROM wardrobe_items WHERE owner_id=?", (A,)).fetchone()[0] == 0
    assert not list((path.parent / "uploads").rglob("*.jpg"))


def test_startup_removes_expired_quota_without_any_business_request(tmp_path):
    path = tmp_path / "startup.db"
    init_db(path)
    with closing(connect_db(path)) as c, c:
        c.execute("INSERT INTO daily_quotas VALUES (?,?,?,?,?)", ("a" * 64, "2000-01-01", 20, 30, "2000-01-02T00:00:00+08:00"))
    app.dependency_overrides[database_path] = lambda: path
    try:
        with TestClient(app) as http:
            assert http.get("/health").status_code == 200
        with closing(connect_db(path)) as c:
            assert c.execute("SELECT count(*) FROM daily_quotas").fetchone()[0] == 0
    finally:
        app.dependency_overrides.pop(database_path, None)


def test_public_item_ids_do_not_reveal_device_and_responses_cannot_be_cached(api):
    http, path, _ = api
    seed_database(path, owner_id=A)
    seeded = http.get("/api/wardrobe/items", headers=headers(A))
    assert seeded.headers.get("cache-control") == "no-store"
    assert "x-device-id" in seeded.headers.get("vary", "").lower()
    assert all(A.replace("-", "") not in x["id"] for x in seeded.json())
    uploaded = upload(http).json()["items"][0]
    assert A.replace("-", "") not in uploaded["id"]
    photo = http.get(f"/api/wardrobe/items/{uploaded['id']}/photo", headers=headers(A))
    assert photo.headers.get("cache-control") == "no-store"
    assert "x-device-id" in photo.headers.get("vary", "").lower()
    assert http.get("/api/wardrobe/items").headers.get("cache-control") == "no-store"


def test_quota_wait_crossing_midnight_uses_date_after_database_lock(tmp_path, monkeypatch):
    from threading import Event

    from app import db
    path = tmp_path / "crossing.db"
    init_db(path)
    old_time = datetime(2026, 11, 13, 23, 59, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    clock = [old_time]
    original_day, original_key = db._quota_day, db.quota_key
    entered = Event()
    def key(*args):
        result = original_key(*args)
        entered.set()
        return result
    monkeypatch.setattr(db, "quota_key", key)
    monkeypatch.setattr(db, "_quota_day", lambda now=None: original_day(clock[0]))
    with closing(connect_db(path)) as c:
        c.execute("BEGIN IMMEDIATE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(db.reserve_quota, path, A, "recognition")
            assert entered.wait(3)
            clock[0] = old_time + timedelta(seconds=1)
            c.execute("DELETE FROM daily_quotas WHERE day < '2026-11-14'")
            c.commit()
            pending.result(timeout=3)
        rows = c.execute("SELECT day, recognition FROM daily_quotas").fetchall()
        assert [(x["day"], x["recognition"]) for x in rows] == [("2026-11-14", 1)]


def test_opaque_migration_updates_existing_owned_references_and_seed_stays_idempotent(tmp_path):
    from app.db import to_db_values
    from app.models import OutfitItem, OutfitSet, Session, WardrobeItem
    path = tmp_path / "old-ids.db"
    init_db(path)
    old = A.replace("-", "") + ":W01"
    records = [
        ("wardrobe_items", WardrobeItem(id=old, owner_id=A, category="top")),
        ("sessions", Session(id="owned-session", owner_id=A, temp_c=18, occasion="commute", formality_target=(1, 5), prompt_version="test")),
        ("outfit_sets", OutfitSet(id="owned-set", owner_id=A, session_id="owned-session", rank=1, reason="正式度合适")),
        ("outfit_items", OutfitItem(set_id="owned-set", item_id=old, owner_id=A, slot="top")),
    ]
    with closing(connect_db(path)) as c, c:
        for table, record in records:
            values = to_db_values(record)
            c.execute(f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join(':'+k for k in values)})", values)
        c.execute("PRAGMA user_version=3")
    init_db(path)
    init_db(path)
    with closing(connect_db(path)) as c:
        row = c.execute("SELECT id FROM wardrobe_items WHERE owner_id=?", (A,)).fetchone()
        assert row["id"] != old and A.replace("-", "") not in row["id"]
        assert c.execute("SELECT item_id FROM outfit_items WHERE owner_id=?", (A,)).fetchone()[0] == row["id"]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    inserted, total = seed_database(path, owner_id=A)
    reference_count = len(json.loads((ROOT / "cases/cases.json").read_text())["wardrobe"])
    assert inserted == reference_count - 1 and total == reference_count


def test_unexpected_api_error_also_disables_cache(api):
    http, path, _ = api
    app.dependency_overrides[database_path] = lambda: path / "invalid.db"
    response = http.get("/api/wardrobe/items", headers=headers(A))
    assert response.status_code == 500
    assert response.headers.get("cache-control") == "no-store"


def test_owner_lock_files_are_bounded_not_permanent_device_identifiers(tmp_path):
    from app.db import owner_lock
    path = tmp_path / "locks.db"
    init_db(path)
    for _ in range(128):
        with owner_lock(path, str(uuid4())):
            pass
    files = list((path.parent / ".owner-locks").glob("*.lock"))
    assert 0 < len(files) <= 64
    assert all(p.stem.isdecimal() and 0 <= int(p.stem) < 64 for p in files)
