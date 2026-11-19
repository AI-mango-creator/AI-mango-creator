import json
from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.db import connect_db, init_db, issue_tryon_ticket, reserve_tryon

A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'


def ready(path):
    init_db(path)
    with closing(connect_db(path)) as db, db:
        db.execute("INSERT INTO experience_products(id,title,category,image_path,source_label,rights_note,content_hash,created_at,sources) VALUES ('p1','体验上装','tops','uploads/catalog/p1/x.jpg','本人拍摄','允许测试','hash',0,'{}')")


def test_reservation_idempotent_and_deleted_request_cannot_rebill(tmp_path):
    path=tmp_path/'app.db'; ready(path); init_db(path)
    ticket=issue_tryon_ticket(path,A,'p1')['ticket']
    job,reused=reserve_tryon(path,A,'p1',ticket,'digest')
    assert not reused
    assert reserve_tryon(path,A,'p1',ticket,'digest') == (job,True)
    with pytest.raises(HTTPException) as conflict:
        reserve_tryon(path,A,'p1',ticket,'different')
    assert conflict.value.status_code==409
    with closing(connect_db(path)) as db,db:
        assert db.execute('select tryon from tryon_daily_quotas').fetchone()[0]==1
        row=dict(db.execute('select * from tryon_daily_quotas').fetchone())
        assert A not in json.dumps(row) and 'digest' not in json.dumps(row)
        db.execute('delete from tryon_jobs')
    with pytest.raises(HTTPException) as deleted:
        reserve_tryon(path,A,'p1',ticket,'digest')
    assert deleted.value.status_code==410


def test_ticket_owner_and_expiry_and_quota(tmp_path):
    path=tmp_path/'app.db';ready(path)
    now=datetime(2026,11,19,23,59,tzinfo=ZoneInfo('Asia/Shanghai'))
    ticket=issue_tryon_ticket(path,A,'p1',now=now)['ticket']
    for owner,at in [(B,now),(A,datetime(2026,11,20,0,0,tzinfo=now.tzinfo))]:
        with pytest.raises(HTTPException):reserve_tryon(path,owner,'p1',ticket,'x',now=at)
    for _ in range(3):reserve_tryon(path,A,'p1',issue_tryon_ticket(path,A,'p1')['ticket'],'x')
    with pytest.raises(HTTPException) as limit:
        reserve_tryon(path,A,'p1',issue_tryon_ticket(path,A,'p1')['ticket'],'x')
    assert limit.value.status_code==429


def test_replayed_tryon_migration_preserves_quota_columns(tmp_path):
    path=tmp_path/'app.db';ready(path)
    ticket=issue_tryon_ticket(path,A,'p1')['ticket'];reserve_tryon(path,A,'p1',ticket,'x')
    with closing(connect_db(path)) as db,db:
        before=dict(db.execute('select * from tryon_daily_quotas').fetchone())
        db.execute('pragma user_version=7')
    init_db(path)
    with closing(connect_db(path)) as db:
        assert dict(db.execute('select * from tryon_daily_quotas').fetchone())==before


def test_concurrent_duplicate_reservations_charge_only_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'app.db';ready(path);ticket=issue_tryon_ticket(path,A,'p1')['ticket']
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda _:reserve_tryon(path,A,'p1',ticket,'x'),range(8)))
    assert len({row[0]['id'] for row in rows})==1
    assert sum(not row[1] for row in rows)==1
    with closing(connect_db(path)) as db:
        assert db.execute('select tryon from tryon_daily_quotas').fetchone()[0]==1


def test_shared_limit_and_expiry_of_anonymous_ledger(tmp_path,monkeypatch):
    from uuid import uuid4

    from app.db import expire_quotas
    path=tmp_path/'app.db';ready(path);monkeypatch.setenv('APP_SHARE_MODE','1')
    now=datetime(2026,11,19,12,tzinfo=ZoneInfo('Asia/Shanghai'))
    for _ in range(10):
        owner=str(uuid4());ticket=issue_tryon_ticket(path,owner,'p1',now=now)['ticket']
        reserve_tryon(path,owner,'p1',ticket,'x',now=now)
    with pytest.raises(HTTPException) as limit:
        reserve_tryon(path,A,'p1',issue_tryon_ticket(path,A,'p1',now=now)['ticket'],'x',now=now)
    assert limit.value.status_code==429
    expire_quotas(path,now=datetime(2026,11,20,0,tzinfo=now.tzinfo))
    with closing(connect_db(path)) as db:
        assert db.execute('select count(*) from tryon_daily_quotas').fetchone()[0]==0
