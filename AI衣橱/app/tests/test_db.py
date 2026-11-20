import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db import connect_db, init_db, to_db_values
from app.models import (
    BodyProfile,
    CommunityAuthor,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityMedia,
    CommunityOption,
    CommunityPost,
    CommunityVote,
    DailyQuota,
    ExperienceProduct,
    OutfitItem,
    OutfitSet,
    PersonalFavorite,
    PersonalFeedback,
    PersonalOotd,
    PersonalSettings,
    PersonalWriteReceipt,
    PointDailyClaim,
    PointEntry,
    Session,
    TryonDailyQuota,
    TryonJob,
    WardrobeItem,
)
from scripts.seed import seed_database

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = PROJECT_ROOT / "cases" / "cases.json"

# 衣柜规模从唯一数据源读取，不在测试里写死：每次扩充衣柜都不应导致测试变红。
WARDROBE_SIZE = len(json.loads(CASES_PATH.read_text(encoding="utf-8"))["wardrobe"])


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "data" / "app.db"
    init_db(path)
    return path


def insert_record(connection, table, record):
    values = to_db_values(record)
    columns = ", ".join(values)
    parameters = ", ".join(f":{column}" for column in values)
    connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({parameters})", values
    )


def create_outfit(connection):
    insert_record(
        connection,
        "sessions",
        Session(
            id="S01", temp_c=18, occasion="commute",
            formality_target=(3, 5), prompt_version="outfit_compose.v1",
        ),
    )
    insert_record(
        connection,
        "outfit_sets",
        OutfitSet(id="O01", session_id="S01", rank=1, reason="18℃通勤选择正式度合适的单品。"),
    )


def test_init_creates_four_tables_matching_models(database):
    expected = {
        "personal_settings": PersonalSettings, "point_entries": PointEntry, "point_daily_claims": PointDailyClaim,
        "personal_favorites": PersonalFavorite, "personal_ootds": PersonalOotd,
        "personal_feedback": PersonalFeedback, "personal_write_receipts": PersonalWriteReceipt,
        "wardrobe_items": WardrobeItem,
        "outfit_sets": OutfitSet,
        "outfit_items": OutfitItem,
        "sessions": Session,
        "body_profiles": BodyProfile,
        "experience_products": ExperienceProduct, "tryon_jobs": TryonJob,
        "community_authors": CommunityAuthor, "community_posts": CommunityPost,
        "community_media": CommunityMedia, "community_likes": CommunityLike,
        "community_follows": CommunityFollow, "community_comments": CommunityComment,
        "community_poll_options": CommunityOption, "community_votes": CommunityVote,
    }
    with closing(connect_db(database)) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == set(expected) | {"daily_quotas", "tryon_daily_quotas"}
        assert {r[1] for r in connection.execute("PRAGMA table_info(tryon_daily_quotas)")} == set(TryonDailyQuota.model_fields)
        quota_columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_quotas)")}
        assert quota_columns == set(DailyQuota.model_fields)
        for table, model in expected.items():
            columns = {row[1]: row[2] for row in connection.execute(f"PRAGMA table_info({table})")}
            assert set(columns) == set(model.model_fields)
            assert columns["sources"] == "TEXT"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert (database.parent / "uploads").is_dir()


def test_seed_is_idempotent_and_preserves_all_reference_attributes(database):
    reference = json.loads(CASES_PATH.read_text())["wardrobe"]
    assert seed_database(database) == (WARDROBE_SIZE, WARDROBE_SIZE)
    assert seed_database(database) == (0, WARDROBE_SIZE)
    with closing(connect_db(database)) as connection:
        rows = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM wardrobe_items")}
    assert len(rows) == WARDROBE_SIZE
    for item in reference:
        saved = rows[item["id"]]
        for field, expected in item.items():
            actual = json.loads(saved[field]) if field in {"colors", "seasons"} else saved[field]
            assert actual == expected, (item["id"], field)
        sources = json.loads(saved["sources"])
        assert sources["id"] == "derived"
        assert sources["category"] == "model"
        assert sources["material"] == "model"
        assert sources["confidence"] == "model"
        assert saved["confidence"] is None
        assert saved["image_path"] is None


def test_seed_preserves_existing_user_edit(database):
    seed_database(database)
    with closing(connect_db(database)) as connection, connection:
        connection.execute(
            "UPDATE wardrobe_items SET sub=?, sources=json_set(sources, '$.sub', 'user') WHERE id=?",
            ("用户改过的衬衫", "W01"),
        )
    assert seed_database(database) == (0, WARDROBE_SIZE)
    with closing(connect_db(database)) as connection:
        item = connection.execute("SELECT sub, sources FROM wardrobe_items WHERE id='W01'").fetchone()
    assert item["sub"] == "用户改过的衬衫"
    assert json.loads(item["sources"])["sub"] == "user"


def test_unique_slot_rejects_two_tops_in_one_outfit(database):
    seed_database(database)
    with closing(connect_db(database)) as connection, connection:
        create_outfit(connection)
        insert_record(connection, "outfit_items", OutfitItem(set_id="O01", item_id="W01", slot="top"))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            insert_record(connection, "outfit_items", OutfitItem(set_id="O01", item_id="W07", slot="top"))
        assert connection.execute("SELECT count(*) FROM outfit_items").fetchone()[0] == 1


def test_foreign_key_rejects_item_outside_wardrobe(database):
    seed_database(database)
    with closing(connect_db(database)) as connection, connection:
        create_outfit(connection)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            insert_record(connection, "outfit_items", OutfitItem(set_id="O01", item_id="W99", slot="top"))


@pytest.mark.parametrize("changes", [
    {"category": "bag"}, {"seasons": ["monsoon"]}, {"warmth": 6},
    {"formality": 0}, {"confidence": 1.1}, {"sources": {"colors": "unknown"}},
])
def test_wardrobe_model_rejects_invalid_enums_and_ranges(changes):
    reference = json.loads(CASES_PATH.read_text())["wardrobe"][0]
    with pytest.raises(ValidationError):
        WardrobeItem.model_validate(reference | changes)


def test_sources_allow_user_color_without_relabeling_confidence():
    reference = json.loads(CASES_PATH.read_text())["wardrobe"][0]
    item = WardrobeItem.model_validate(reference | {"sources": {"colors": "user"}})
    assert item.sources["colors"] == "user"
    assert item.sources["confidence"] == "model"
    assert item.sources["id"] == "derived"
    assert set(item.sources) == set(WardrobeItem.model_fields)


def test_database_rejects_invalid_category(database):
    seed_database(database)
    with (
        closing(connect_db(database)) as connection,
        connection,
        pytest.raises(sqlite3.IntegrityError, match="CHECK"),
    ):
        connection.execute("UPDATE wardrobe_items SET category='bag' WHERE id='W01'")


def test_database_preserves_unknown_attributes_as_null(database):
    item = WardrobeItem(
        id="manual-01", category="top", colors=["蓝色"],
        sources={"category": "user", "colors": "user"},
    )
    with closing(connect_db(database)) as connection, connection:
        insert_record(connection, "wardrobe_items", item)
        saved = connection.execute(
            "SELECT warmth, formality, confidence FROM wardrobe_items WHERE id=?", (item.id,)
        ).fetchone()
    assert tuple(saved) == (None, None, None)


def test_invalid_seed_is_rejected_before_database_creation(tmp_path):
    source = json.loads(CASES_PATH.read_text())
    source["wardrobe"][-1]["warmth"] = 99
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(source))
    database = tmp_path / "invalid.db"
    with pytest.raises(ValidationError):
        seed_database(database, invalid)
    assert not database.exists()


def test_seed_cli_uses_temporary_database(tmp_path):
    database = tmp_path / "cli.db"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed", "--database", str(database)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"共 {WARDROBE_SIZE} 件" in result.stdout
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == WARDROBE_SIZE


def test_seed_cli_returns_chinese_error_without_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed", "--database", str(tmp_path / "error.db"),
         "--cases", str(tmp_path / "missing.json")],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "初始化衣柜失败" in result.stderr
    assert "Traceback" not in result.stderr


def test_owner_migration_preserves_legacy_rows_and_is_repeatable(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript((PROJECT_ROOT / "app/migrations/001_init.sql").read_text())
        item = WardrobeItem.model_validate(json.loads(CASES_PATH.read_text())["wardrobe"][0])
        values = to_db_values(item)
        values.pop("owner_id", None)
        # 001历史表没有后续006的管理分类列；明确构造历史数据，不删验收断言。
        values.pop("wardrobe_group", None)
        connection.execute(f"INSERT INTO wardrobe_items ({', '.join(values)}) VALUES ({', '.join(':'+k for k in values)})", values)
    init_db(path)
    init_db(path)
    with closing(connect_db(path)) as connection:
        row = connection.execute("SELECT * FROM wardrobe_items").fetchone()
        assert "owner_id" in dict(row)
        assert row["owner_id"] == "legacy"
        assert row["id"] == item.id and row["sub"] == item.sub
        assert json.loads(row["sources"])["owner_id"] == "derived"
        for table in ("wardrobe_items", "sessions", "outfit_sets", "outfit_items"):
            columns = {r["name"]: r for r in connection.execute(f"PRAGMA table_info({table})")}
            assert columns["owner_id"]["notnull"] == 1
        assert connection.execute("SELECT count(*) FROM wardrobe_items").fetchone()[0] == 1
        assert row['wardrobe_group'] == item.wardrobe_group


def test_seed_scopes_two_explicit_devices_without_changing_cases(database):
    from uuid import uuid4
    owner_a, owner_b = str(uuid4()), str(uuid4())
    assert seed_database(database, owner_id=owner_a) == (WARDROBE_SIZE, WARDROBE_SIZE)
    assert seed_database(database, owner_id=owner_b) == (WARDROBE_SIZE, WARDROBE_SIZE)
    assert seed_database(database, owner_id=owner_a) == (0, WARDROBE_SIZE)
    with closing(connect_db(database)) as connection:
        for owner in (owner_a, owner_b):
            rows = connection.execute("SELECT * FROM wardrobe_items WHERE owner_id=?", (owner,)).fetchall()
            assert len(rows) == WARDROBE_SIZE
            assert {row["sub"] for row in rows} == {x["sub"] for x in json.loads(CASES_PATH.read_text())["wardrobe"]}


def test_cross_owner_outfit_reference_is_rejected(database):
    from uuid import uuid4
    owner_a, owner_b = str(uuid4()), str(uuid4())
    item = WardrobeItem(id="A-top", category="top", owner_id=owner_a)
    with closing(connect_db(database)) as connection, connection:
        insert_record(connection, "wardrobe_items", item)
        insert_record(connection, "sessions", Session(id="B-session", owner_id=owner_b, temp_c=18,
                      occasion="commute", formality_target=(1, 5), prompt_version="test"))
        insert_record(connection, "outfit_sets", OutfitSet(id="B-set", owner_id=owner_b,
                      session_id="B-session", rank=1, reason="正式度合适"))
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            insert_record(connection, "outfit_items", OutfitItem(set_id="B-set", item_id="A-top", slot="top", owner_id=owner_b))


def test_claim_legacy_is_dry_run_until_apply_and_claims_all_four_tables(database):
    from uuid import uuid4

    from scripts.claim_legacy import claim_legacy
    owner = str(uuid4())
    seed_database(database)
    with closing(connect_db(database)) as connection, connection:
        create_outfit(connection)
        insert_record(connection, "outfit_items", OutfitItem(set_id="O01", item_id="W01", slot="top"))
    counts = claim_legacy(database, device_id=owner)
    assert counts == {"wardrobe_items": WARDROBE_SIZE, "sessions": 1, "outfit_sets": 1, "outfit_items": 1}
    with closing(connect_db(database)) as connection:
        assert connection.execute("SELECT owner_id FROM wardrobe_items LIMIT 1").fetchone()[0] == "legacy"
    assert claim_legacy(database, device_id=owner, apply=True) == counts
    assert set(claim_legacy(database, device_id=owner, apply=True).values()) == {0}
    with closing(connect_db(database)) as connection:
        for table, count in counts.items():
            assert connection.execute(f"SELECT count(*) FROM {table} WHERE owner_id=?", (owner,)).fetchone()[0] == count
            assert connection.execute(f"SELECT count(*) FROM {table} WHERE owner_id='legacy'").fetchone()[0] == 0


def test_claim_cli_default_is_read_only(database):
    from uuid import uuid4
    seed_database(database)
    before = database.read_bytes()
    command = [sys.executable, "-m", "scripts.claim_legacy", "--database", str(database), "--device-id", str(uuid4())]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "dry-run" in result.stdout
    assert database.read_bytes() == before


def test_owner_migration_parallel_startup_and_nonnull(database):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(init_db, [database] * 8))
    seed_database(database)
    with closing(connect_db(database)) as connection, connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] >= 2
        for table in ("wardrobe_items", "sessions", "outfit_sets", "outfit_items"):
            assert [r["name"] for r in connection.execute(f"PRAGMA table_info({table})")].count("owner_id") == 1
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            connection.execute("UPDATE wardrobe_items SET owner_id=NULL WHERE id='W01'")
