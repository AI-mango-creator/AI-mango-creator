from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.db import connect_db, expire_quotas, init_db
from app.main import app
from app.routers.wardrobe import database_path

A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'

@pytest.fixture
def me_api(tmp_path):
    path=tmp_path/'app.db'; init_db(path)
    app.dependency_overrides[database_path]=lambda:path
    try:
        with TestClient(app,headers={'X-Device-ID':A}) as c:
            yield c,path
    finally:
        app.dependency_overrides.pop(database_path,None)


def test_checkin_is_real_repeat_safe_and_owner_scoped(me_api):
    c,path=me_api
    assert c.get('/api/me/points').status_code==200
    assert c.get('/api/me/points').json()['balance']==0
    r=c.post('/api/me/points/check-in'); assert r.status_code==200,r.text
    assert r.json()['balance']==10 and r.json()['awarded']
    assert c.post('/api/me/points/check-in').json()['awarded'] is False
    assert c.get('/api/me/points').json()['balance']==10
    assert len(c.get('/api/me/points').json()['items'])==1
    assert c.get('/api/me/points',headers={'X-Device-ID':B}).json()['balance']==0
    assert c.post('/api/me/points/check-in',json={'delta':999}).status_code==400
    assert c.get('/api/me/points',headers={'X-Device-ID':''}).status_code==400
    with closing(connect_db(path)) as db:
        assert db.execute('select count(*) from point_entries').fetchone()[0]==1


def test_parallel_checkin_and_midnight(me_api):
    from app.services.personal import check_in
    _,path=me_api
    early=datetime(2026,11,20,23,59,tzinfo=ZoneInfo('Asia/Shanghai'))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _:check_in(path,A,now=early),range(12)))
    assert sum(x['awarded'] for x in results)==1
    assert check_in(path,A,now=datetime(2026,11,21,0,0,tzinfo=early.tzinfo))['balance']==20


def test_migration_repeated_and_expiration_keeps_private_ledger(me_api):
    from app.services.personal import check_in
    _,path=me_api
    then=datetime(2026,11,20,12,tzinfo=ZoneInfo('Asia/Shanghai'))
    check_in(path,A,now=then);init_db(path);init_db(path)
    expire_quotas(path,now=datetime(2026,11,21,tzinfo=then.tzinfo))
    with closing(connect_db(path)) as db:
        assert db.execute('select sum(delta) from point_entries').fetchone()[0]==10
        assert db.execute('select count(*) from point_daily_claims').fetchone()[0]==0


def test_ticket_binds_owner_purpose_content_and_expiry(me_api):
    from fastapi import HTTPException

    from app.services import personal
    c,path=me_api
    r=c.post('/api/me/write-tickets?purpose=ootd');assert r.status_code==200,r.text
    token=r.json()['ticket']
    with closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(HTTPException) as error:
            personal.consume_ticket(db,path,B,token,'ootd',{'a':1})
        assert error.value.status_code==410
        value=personal.consume_ticket(db,path,A,token,'ootd',{'a':1})
        assert value['fresh']
        assert not personal.consume_ticket(db,path,A,token,'ootd',{'a':1})['fresh']
        with pytest.raises(HTTPException) as error:
            personal.consume_ticket(db,path,A,token,'ootd',{'a':2})
        assert error.value.status_code==409
    assert c.post('/api/me/write-tickets?purpose=clear').status_code==400
    assert c.post('/api/me/write-tickets?purpose=bad').status_code==400
