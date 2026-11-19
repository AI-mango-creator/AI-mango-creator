import base64
import json
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect_db, init_db
from app.llm import client
from app.llm.errors import LLMError
from app.main import app
from app.models import ProviderTryon
from app.routers.wardrobe import database_path
from scripts.import_tryon_catalog import import_catalog

A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
PHOTO=Path(__file__).resolve().parents[2]/'cases/images/cloth01.jpg'


@pytest.fixture
def api(tmp_path,monkeypatch):
    path=tmp_path/'app.db';init_db(path)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps([{'id':'p1','title':'离线测试款','category':'tops','photo':str(PHOTO),'source_label':'测试夹具','rights_note':'仅离线测试'}]))
    import_catalog(manifest,path,apply=True)
    app.dependency_overrides[database_path]=lambda:path
    calls=[]
    monkeypatch.setattr(client,'tryon_configuration',lambda:'test-key')
    def submit(*args):calls.append(args);return ProviderTryon(id='provider-task')
    monkeypatch.setattr(client,'tryon_submit',submit)
    monkeypatch.setattr(client,'tryon_status',lambda _:ProviderTryon(id='provider-task',status='completed',output=['data:image/jpeg;base64,'+base64.b64encode(PHOTO.read_bytes()).decode()]))
    try:
        with TestClient(app,headers={'X-Device-ID':A}) as http:yield http,path,calls
    finally:app.dependency_overrides.pop(database_path,None)


def create(http,ticket=None):
    ticket=ticket or http.get('/api/tryons/ticket',params={'product_id':'p1'}).json()['ticket']
    return http.post('/api/tryons',data={'product_id':'p1','ticket':ticket,'consent':'true'},files={'photo':('person.jpg',PHOTO.read_bytes(),'image/jpeg')})


def test_tryon_complete_owner_isolated_idempotent_and_deleted_ledger(api):
    http,path,calls=api
    products=http.get('/api/experience/products').json();assert products[0]['title']=='离线测试款'
    assert 'image_path' not in json.dumps(products)
    ticket=http.get('/api/tryons/ticket?product_id=p1').json()['ticket']
    r=create(http,ticket);assert r.status_code==202,r.text
    task=r.json();assert task['status']=='starting'
    assert create(http,ticket).json()['id']==task['id'] and len(calls)==1
    assert http.get('/api/tryons/'+task['id'],headers={'X-Device-ID':B}).status_code==404
    ready=http.get('/api/tryons/'+task['id']).json();assert ready['status']=='completed' and ready['has_result']
    assert http.get('/api/tryons/'+task['id']+'/result').content==PHOTO.read_bytes()
    assert http.get('/api/tryons/'+task['id']+'/result',headers={'X-Device-ID':B}).status_code==404
    assert 'provider-task' not in json.dumps(ready)
    assert http.delete('/api/tryons/'+task['id']).status_code==204
    assert create(http,ticket).status_code==410 and len(calls)==1
    assert not list((path.parent/'uploads'/A/'tryon').rglob('*.jpg'))


def test_unknown_submission_no_automatic_retry_or_rebilling(api,monkeypatch):
    http,path,calls=api
    def timeout(*args):calls.append('timeout');raise LLMError('MODEL_TIMEOUT','sensitive')
    monkeypatch.setattr(client,'tryon_submit',timeout)
    ticket=http.get('/api/tryons/ticket?product_id=p1').json()['ticket']
    task=create(http,ticket).json();assert task['status']=='unknown'
    assert create(http,ticket).json()['status']=='unknown' and len(calls)==1
    assert http.get('/api/tryons/'+task['id']).json()['status']=='unknown'
    assert http.delete('/api/wardrobe/items').status_code==200
    assert create(http,ticket).status_code==410 and len(calls)==1
    with closing(connect_db(path)) as db:assert db.execute('select tryon from tryon_daily_quotas').fetchone()[0]==1


def test_consent_and_configuration_do_not_charge_or_submit(api,monkeypatch):
    http,path,calls=api
    ticket=http.get('/api/tryons/ticket?product_id=p1').json()['ticket']
    r=http.post('/api/tryons',data={'product_id':'p1','ticket':ticket,'consent':'false'},files={'photo':('x.jpg',PHOTO.read_bytes(),'image/jpeg')})
    assert r.status_code==422 and not calls
    def missing():raise LLMError('MODEL_CONFIG','请配置FASHN_API_KEY')
    monkeypatch.setattr(client,'tryon_configuration',missing)
    assert create(http,ticket).status_code==503 and not calls
    with closing(connect_db(path)) as db:assert db.execute('select count(*) from tryon_jobs').fetchone()[0]==0


def test_polling_is_throttled_and_malformed_result_is_rejected(api,monkeypatch):
    http,path,_calls=api;task=create(http).json();polls=[]
    def pending(_):polls.append(1);return ProviderTryon(id='provider-task',status='processing')
    monkeypatch.setattr(client,'tryon_status',pending)
    assert http.get('/api/tryons/'+task['id']).json()['status']=='processing'
    assert http.get('/api/tryons/'+task['id']).json()['status']=='processing' and len(polls)==1
    with closing(connect_db(path)) as db,db:db.execute('update tryon_jobs set last_poll=0')
    monkeypatch.setattr(client,'tryon_status',lambda _:ProviderTryon(id='provider-task',status='completed',output=['https://unexpected.example/image.jpg']))
    assert http.get('/api/tryons/'+task['id']).json()['status']=='failed'
    assert http.get('/api/tryons/'+task['id']+'/result').status_code==404


def test_clear_during_provider_submit_does_not_resurrect_photos(api,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    http,path,calls=api;entered,release=Event(),Event()
    def delayed(*args):
        calls.append(1);entered.set();assert release.wait(5);return ProviderTryon(id='late-result')
    monkeypatch.setattr(client,'tryon_submit',delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(create,http);assert entered.wait(3)
        assert http.delete('/api/wardrobe/items').status_code==200
        release.set();assert pending.result().status_code==404
    with closing(connect_db(path)) as db:
        assert db.execute('select count(*) from tryon_jobs').fetchone()[0]==0
        assert db.execute('select tryon from tryon_daily_quotas').fetchone()[0]==1
    assert not (path.parent/'uploads'/A).exists()


def test_clear_during_status_does_not_write_late_result(api,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    http,path,_=api;task=create(http).json();entered,release=Event(),Event()
    original=client.tryon_status
    def delayed(task_id):entered.set();assert release.wait(5);return original(task_id)
    monkeypatch.setattr(client,'tryon_status',delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(http.get,'/api/tryons/'+task['id']);assert entered.wait(3)
        assert http.delete('/api/wardrobe/items').status_code==200
        release.set();assert pending.result().status_code==404
    assert not (path.parent/'uploads'/A).exists()


def test_poll_budget_is_terminal_and_never_regenerates(api,monkeypatch):
    http,path,calls=api;task=create(http).json()
    with closing(connect_db(path)) as db,db:db.execute('update tryon_jobs set polls=30')
    monkeypatch.setattr(client,'tryon_status',lambda _:pytest.fail('poll budget exceeded'))
    assert http.get('/api/tryons/'+task['id']).json()['status']=='timed_out'
    assert len(calls)==1


def test_stale_submission_is_unknown_without_resubmitting(api):
    from time import time
    http,path,calls=api;task=create(http).json()
    with closing(connect_db(path)) as db,db:
        db.execute("update tryon_jobs set status='submitting',provider_task_id=NULL,created_at=?",(time()-30,))
    assert http.get('/api/tryons/'+task['id']).json()['status']=='unknown'
    assert len(calls)==1


def test_ambiguous_local_error_after_submit_is_not_definite_failure(api,monkeypatch):
    http,_,_=api
    def ambiguous(*args):raise LLMError('MODEL_CONFIG','日志写入失败')
    monkeypatch.setattr(client,'tryon_submit',ambiguous)
    assert create(http).json()['status']=='unknown'


def test_configuration_response_is_user_facing_not_environment_instructions(api,monkeypatch):
    http,_,_=api
    def missing():raise LLMError('MODEL_CONFIG','FASHN_API_KEY internal')
    monkeypatch.setattr(client,'tryon_configuration',missing)
    response=create(http)
    assert response.status_code==503
    assert 'FASHN_API_KEY' not in response.text
    assert '试穿' in response.json()['detail']


def test_provider_calls_have_local_task_log_context(api,monkeypatch):
    http,_,_=api;contexts=[]
    def submit(*args):
        context=client._request.get()
        assert context is not None
        contexts.append(context.case_id)
        return ProviderTryon(id='logged-provider')
    monkeypatch.setattr(client,'tryon_submit',submit)
    task=create(http).json()
    assert contexts==[task['id']]
