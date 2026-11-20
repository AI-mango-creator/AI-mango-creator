import json
from contextlib import closing
from pathlib import Path

from app.db import connect_db
from app.tests.test_personal_api import A, B
from app.tests.test_personal_api import me_api as _me_api

me_api = _me_api

PHOTO=Path('cases/images/cloth01.jpg').read_bytes()


def create(c, *, owner=A, ticket=None, **fields):
    ticket=ticket or c.post('/api/me/write-tickets?purpose=ootd',headers={'X-Device-ID':owner}).json()['ticket']
    values={'ticket':ticket,'worn_on':'2026-11-20','kind':'photo',**fields}
    return c.post('/api/me/ootds',headers={'X-Device-ID':owner},data={'metadata':json.dumps(values)},files=[('photo',('ootd.jpg',PHOTO,'image/jpeg'))] if values['kind']=='photo' else None)


def test_private_photo_persists_edit_delete_and_old_post_cannot_revive(me_api):
    c,path=me_api
    ticket=c.post('/api/me/write-tickets?purpose=ootd').json()['ticket']
    r=create(c,ticket=ticket);assert r.status_code==201,r.text
    oid=r.json()['id'];url='/api/me/ootds/'+oid
    assert create(c,ticket=ticket).status_code==200
    assert create(c,ticket=ticket,title='变了').status_code==409
    assert len(c.get('/api/me/ootds').json()['items'])==1
    assert c.get(url+'/photo').content==PHOTO
    assert c.get(url,headers={'X-Device-ID':B}).status_code==404
    assert c.get(url+'/photo',headers={'X-Device-ID':B}).status_code==404
    assert c.patch(url,json={'worn_on':'2026-11-19','title':'通勤','note':'舒服'}).json()['title']=='通勤'
    assert c.delete(url).status_code==204
    assert c.delete(url).status_code==404
    assert create(c,ticket=ticket).status_code==410
    assert not list((path.parent/'uploads'/A/'personal').rglob('*.jpg'))


def test_source_owner_and_deleted_source_tombstone(me_api):
    c,path=me_api
    from app.models import OutfitSet, Session
    from app.services.personal import insert
    with closing(connect_db(path)) as db,db:
        insert(db,'sessions',Session(id='session',owner_id=A,temp_c=18,occasion='commute',formality_target=(2,4),prompt_version='v1'))
        insert(db,'outfit_sets',OutfitSet(id='set',session_id='session',owner_id=A,rank=1,reason='温度18度'))
    assert create(c,owner=B,kind='outfit',set_id='set').status_code==404
    r=create(c,kind='outfit',set_id='set');assert r.status_code==201,r.text
    with closing(connect_db(path)) as db,db:
        db.execute('DELETE FROM outfit_sets WHERE id=?',('set',))
    data=c.get('/api/me/ootds/'+r.json()['id']).json()
    assert data['source_deleted'] and data['set_id'] is None
    assert c.delete('/api/me/ootds/'+r.json()['id']).status_code==204
    with closing(connect_db(path)) as db:
        assert db.execute('select count(*) from sessions').fetchone()[0]==1


def test_same_date_multiple_records_and_invalid_dates(me_api):
    c,_=me_api
    assert create(c).status_code==201 and create(c).status_code==201
    assert len(c.get('/api/me/ootds').json()['items'])==2
    assert create(c,worn_on='2026-02-30').status_code==400
    assert c.get('/api/me/ootds?limit=21').status_code==400
