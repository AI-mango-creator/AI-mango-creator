import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.models import SourcedModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("APP_DATA_DIR", PROJECT_ROOT / "data")) / "app.db"
MIGRATION_PATH = Path(__file__).resolve().parent / "migrations" / "001_init.sql"


def connect_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    path = Path(db_path)
    (path.parent / "uploads").mkdir(parents=True, exist_ok=True)
    with closing(connect_db(path)) as connection, connection:
        try:
            connection.create_function("opaque_item_id", 2,
                                       lambda owner, item: opaque_item_id(path, owner, item), deterministic=True)
            # DDL与版本号同一事务；锁内重新读版本，重复/并发启动都不重复加列。
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            for migration in sorted(MIGRATION_PATH.parent.glob("[0-9][0-9][0-9]_*.sql")):
                number = int(migration.name.split("_", 1)[0])
                if number <= version:
                    continue
                statement = ""
                for line in migration.read_text(encoding="utf-8").splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        if statement.strip().upper() not in {"BEGIN;", "COMMIT;"}:
                            connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise sqlite3.OperationalError("迁移SQL语句不完整。")
                connection.execute(f"PRAGMA user_version = {number}")
        except sqlite3.Error:
            connection.rollback()
            raise


def to_db_values(record: SourcedModel) -> dict:
    values = record.model_dump(mode="json")
    return {
        field: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
        for field, value in values.items()
    }


# 配额只保留匿名当日计数；盐和锁均在忽略提交的本地data目录。
def quota_key(db_path: Path, owner_id: str) -> str:
    import fcntl
    import hashlib
    import os
    import secrets
    from uuid import UUID

    owner_id = str(UUID(owner_id))
    salt_file = Path(db_path).parent / ".quota_salt"
    salt_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(salt_file, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        os.fchmod(stream.fileno(), 0o600)
        salt = stream.read()
        if not salt:
            salt = secrets.token_hex(32).encode("ascii")
            stream.write(salt)
            stream.flush()
            os.fsync(stream.fileno())
    return hashlib.sha256(owner_id.encode("ascii") + salt).hexdigest()


def _quota_day(now=None):
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Shanghai")
    current = (now or datetime.now(zone)).astimezone(zone)
    next_day = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=zone)
    return current, current.date().isoformat(), next_day


def expire_quotas(db_path: Path, *, now=None) -> int:
    _, day, _ = _quota_day(now)
    with closing(connect_db(db_path)) as connection, connection:
        return connection.execute("DELETE FROM daily_quotas WHERE day < ?", (day,)).rowcount


def reserve_quota(db_path: Path, owner_id: str, ability: str, *, now=None) -> None:
    from fastapi import HTTPException

    limits = {"recognition": (20, "识别照片"), "composition": (30, "生成搭配")}
    if ability not in limits:
        raise ValueError("配额能力无效。")
    maximum, label = limits[ability]
    key = quota_key(db_path, owner_id)
    with closing(connect_db(db_path)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        # 取锁可能跨午夜；持写锁后才决定归属日，不能复活昨天的额度行。
        current, day, next_day = _quota_day(now)
        connection.execute("DELETE FROM daily_quotas WHERE day < ?", (day,))
        if os.getenv("APP_SHARE_MODE") == "1":
            total_limit = int(os.getenv(f"APP_SHARE_{ability.upper()}_LIMIT", str(maximum)))
            if total_limit <= 0:
                raise ValueError("分享模式全站配额必须是正整数。")
            total = connection.execute(f"SELECT coalesce(sum({ability}),0) FROM daily_quotas WHERE day=?", (day,)).fetchone()[0]
            if total >= total_limit:
                raise HTTPException(429, f"测试服务今日{label}总额度已用完，请明天再试。",
                                    headers={"Retry-After": str(max(1, int((next_day-current).total_seconds())))})
        connection.execute("INSERT INTO daily_quotas(owner_hash, day, expires_at) VALUES (?,?,?) "
                           "ON CONFLICT(owner_hash, day) DO NOTHING", (key, day, next_day.isoformat()))
        accepted = connection.execute(
            f"UPDATE daily_quotas SET {ability}={ability}+1 WHERE owner_hash=? AND day=? AND {ability}<?",
            (key, day, maximum),
        ).rowcount
    if not accepted:
        raise HTTPException(429, f"今日{label}已达{maximum}次上限，请明天再试。",
                            headers={"Retry-After": str(max(1, int((next_day-current).total_seconds())))})


@contextmanager
def owner_lock(db_path: Path, owner_id: str):
    import fcntl

    directory = Path(db_path).parent / ".owner-locks"
    directory.mkdir(parents=True, exist_ok=True)
    # 固定64桶，不永久保留可关联单个设备的hash文件，也不因任意UUID请求无限增inode。
    bucket = int(quota_key(db_path, owner_id)[:8], 16) % 64
    with (directory / f"{bucket:02}.lock").open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def opaque_item_id(db_path: Path, owner_id: str, reference_id: str) -> str:
    """开发seed与旧owned ID迁移共用映射，不把设备UUID发进URL或模型候选。"""
    import hashlib
    from uuid import UUID

    own_hex = UUID(owner_id).hex
    ordinal = ""
    if reference_id.startswith(own_hex + ":"):
        reference_id = reference_id[len(own_hex) + 1:]
    elif reference_id.startswith("U" + own_hex):
        reference_id, index = reference_id[len(own_hex) + 1:].rsplit("-", 1)
        reference_id = "upload:" + reference_id
        ordinal = "-" + index
    digest = hashlib.sha256((quota_key(db_path, owner_id) + ":item:" + reference_id).encode()).hexdigest()
    return "I" + digest[:32] + ordinal
