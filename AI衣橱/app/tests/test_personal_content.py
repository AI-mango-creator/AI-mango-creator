from app.tests.test_community_api import publish
from app.tests.test_personal_api import A, B
from app.tests.test_personal_api import me_api as _me_api

me_api=_me_api


def write(c,purpose):
    return c.post('/api/me/write-tickets?purpose='+purpose).json()['ticket']


def test_private_content_favorites_publish_and_post_deletion(me_api):
    c,_=me_api
    p=publish(c,owner=B).json();pid=p['id']
    assert c.get('/api/me/content?tab=published').status_code==200
    assert c.get('/api/me/content?tab=published').json()['items']==[]
    url='/api/me/favorites/'+pid
    ticket=write(c,'favorite')
    assert c.put(url,json={'ticket':ticket}).json()=={'saved':True}
    assert c.put(url,json={'ticket':ticket}).json()=={'saved':True}
    assert c.get(url).json()=={'saved':True}
    assert len(c.get('/api/me/content?tab=favorites').json()['items'])==1
    assert c.get('/api/me/content?tab=favorites',headers={'X-Device-ID':B}).json()['items']==[]
    assert c.get('/api/me/content?tab=published',headers={'X-Device-ID':B}).json()['items'][0]['id']==pid
    assert c.delete('/api/community/posts/'+pid,headers={'X-Device-ID':B}).status_code==204
    assert c.get('/api/me/content?tab=favorites').json()['items']==[]
    assert c.get('/api/me').status_code==200


def test_feedback_is_idempotent_and_not_restored_after_clear(me_api):
    c,_=me_api
    body={'ticket':write(c,'feedback'),'category':'feedback','text':'希望支持更多衣柜分类'}
    r=c.post('/api/me/feedback',json=body);assert r.status_code==201,r.text
    assert c.post('/api/me/feedback',json=body).json()['id']==r.json()['id']
    assert c.post('/api/me/feedback',json={**body,'text':'改了'}).status_code==409
    c.delete('/api/wardrobe/items')
    assert c.post('/api/me/feedback',json=body).status_code==410


def test_historical_tryon_reads_local_snapshot_without_provider(me_api,monkeypatch):
    from contextlib import closing

    from app.db import connect_db
    from app.llm import client
    from app.models import ExperienceProduct, TryonJob
    from app.services.personal import insert
    c,path=me_api
    def forbidden(*args,**kwargs):
        raise AssertionError('history must not poll provider')
    monkeypatch.setattr(client,'tryon_status',forbidden)
    with closing(connect_db(path)) as db,db:
        insert(db,'experience_products',ExperienceProduct(id='prod',title='有权素材',category='tops',image_path='unused',source_label='测试',rights_note='有权',content_hash='a'*64,created_at=1))
        insert(db,'tryon_jobs',TryonJob(id='oldtask',owner_id=A,request_id='req',request_hash='a'*64,product_id='prod',status='processing',provider_task_id='external',created_at=1))
    r=c.get('/api/me/tryons/oldtask');assert r.status_code==200,r.text
    assert r.json()['id']=='oldtask' and r.json()['status']=='processing'
    assert c.get('/api/me/tryons/oldtask',headers={'X-Device-ID':B}).status_code==404
