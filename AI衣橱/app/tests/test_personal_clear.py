from contextlib import closing

import pytest

from app.db import connect_db
from app.tests.test_ootd_api import create
from app.tests.test_personal_api import A, B
from app.tests.test_personal_api import me_api as _me_api

me_api = _me_api


def test_clear_removes_private_records_preserves_other_owner_and_same_day_claim(me_api):
    c,path=me_api
    assert c.post('/api/me/points/check-in').json()['balance']==10
    old=c.post('/api/me/write-tickets?purpose=ootd').json()['ticket']
    assert create(c).status_code==201
    assert create(c,owner=B).status_code==201
    assert c.delete('/api/wardrobe/items').status_code==200
    assert c.get('/api/me/ootds').json()['items']==[]
    assert len(c.get('/api/me/ootds',headers={'X-Device-ID':B}).json()['items'])==1
    assert c.post('/api/me/points/check-in').json()=={'awarded':False,'day':c.post('/api/me/points/check-in').json()['day'],'balance':0}
    assert create(c,ticket=old).status_code==410
    assert not (path.parent/'uploads'/A).exists()


def test_clear_rollback_restores_ootd_photo(me_api,monkeypatch):
    from app.services import personal
    c,_=me_api
    r=create(c);oid=r.json()['id']
    def fail(*args):
        raise OSError('injected db cleanup error')
    monkeypatch.setattr(personal,'clear_records',fail)
    with pytest.raises(OSError):
        c.delete('/api/wardrobe/items')
    assert c.get('/api/me/ootds/'+oid+'/photo').status_code==200


def test_clear_recovery_uses_durable_receipt(me_api):
    from app.db import owner_lock
    from app.services import personal
    c,path=me_api
    r=create(c);oid=r.json()['id']
    with owner_lock(path,A):
        operation=personal.prepare_clear(path,A)
        personal.stage_private(path,A,operation)
    assert not (path.parent/'uploads'/A).exists()
    personal.recover_pending_clear(path)
    assert c.get('/api/me/ootds/'+oid+'/photo').status_code==200
    with owner_lock(path,A):
        operation=personal.prepare_clear(path,A)
        personal.stage_private(path,A,operation)
        with closing(connect_db(path)) as db,db:
            db.execute('DELETE FROM personal_ootds WHERE owner_id=?',(A,))
            db.execute("UPDATE personal_write_receipts SET state='consumed' WHERE token_hash=?",(operation,))
    personal.recover_pending_clear(path)
    assert c.get('/api/me/ootds/'+oid).status_code==404
    assert not (path.parent/'uploads'/A).exists()
