"""仅本地开发：不挂HTTP；默认dry-run，显式--apply才认领legacy数据。"""

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import UUID

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import DB_PATH, connect_db

TABLES = ("wardrobe_items", "sessions", "outfit_sets", "outfit_items")


def claim_legacy(database: Path, *, device_id: str, apply: bool = False) -> dict[str, int]:
    owner = str(UUID(device_id))
    path = Path(database)
    if not path.is_file():
        raise ValueError("数据库不存在，请先在本地执行迁移。")
    # dry-run连文件都只读，不触发迁移/写事务/认领。
    connection = connect_db(path) if apply else sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    with closing(connection), connection:
        if apply:
            connection.execute("BEGIN IMMEDIATE")
        counts = {table: connection.execute(f"SELECT count(*) FROM {table} WHERE owner_id='legacy'").fetchone()[0]
                  for table in TABLES}
        if apply:
            for table in TABLES:
                connection.execute(f"UPDATE {table} SET owner_id=?, sources=json_set(sources, '$.owner_id', 'derived') "
                                   "WHERE owner_id='legacy'", (owner,))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--database", type=Path, default=DB_PATH)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        counts = claim_legacy(args.database, device_id=args.device_id, apply=args.apply)
    except (ValueError, OSError, sqlite3.Error):
        print("认领失败：仅本地开发使用，请检查设备UUID、已迁移数据库及其备份。", file=sys.stderr)
        return 1
    print(("已认领" if args.apply else "dry-run（未写库）") + "：" + "，".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
