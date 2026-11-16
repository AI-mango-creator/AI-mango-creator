import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.db import (
    DB_PATH,
    PROJECT_ROOT,
    connect_db,
    init_db,
    opaque_item_id,
    to_db_values,
)
from app.models import SeedData, WardrobeItem

CASES_PATH = PROJECT_ROOT / "cases" / "cases.json"


def seed_database(db_path: Path = DB_PATH, cases_path: Path = CASES_PATH, *, owner_id: str = "legacy") -> tuple[int, int]:
    owner_id = "legacy" if owner_id == "legacy" else str(UUID(owner_id))
    data = SeedData.model_validate_json(Path(cases_path).read_text(encoding="utf-8"))
    for item in data.wardrobe:
        item.owner_id = "legacy" if owner_id == "legacy" else UUID(owner_id)
        if owner_id != "legacy":
            item.id = opaque_item_id(db_path, owner_id, item.id)
    init_db(db_path)
    columns = ", ".join(WardrobeItem.model_fields)
    parameters = ", ".join(f":{field}" for field in WardrobeItem.model_fields)
    with closing(connect_db(db_path)) as connection, connection:
        before = connection.total_changes
        connection.executemany(
            f"INSERT INTO wardrobe_items ({columns}) VALUES ({parameters}) "
            "ON CONFLICT(id) DO NOTHING",
            [to_db_values(item) for item in data.wardrobe],
        )
        inserted = connection.total_changes - before
        total = connection.execute("SELECT count(*) FROM wardrobe_items WHERE owner_id=?", (owner_id,)).fetchone()[0]
    return inserted, total


def main() -> int:
    parser = argparse.ArgumentParser(description="从唯一用例文件初始化本地衣柜。")
    parser.add_argument("--database", type=Path, default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="包含 wardrobe 的用例文件")
    parser.add_argument("--owner-id", default="legacy", help="仅本地开发：指定设备UUID；缺省隔离归legacy")
    arguments = parser.parse_args()
    try:
        inserted, total = seed_database(arguments.database, arguments.cases, owner_id=arguments.owner_id)
    except (OSError, ValidationError, ValueError, sqlite3.Error):
        print("初始化衣柜失败，请检查用例文件、数据字段及数据库目录。", file=sys.stderr)
        return 1
    print(f"衣柜初始化完成：本次新增 {inserted} 件，当前共 {total} 件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
