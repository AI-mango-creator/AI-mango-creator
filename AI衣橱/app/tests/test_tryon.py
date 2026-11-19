import json

import pytest

from app.llm import client
from app.llm.errors import LLMError


class Response:
    def __init__(self,status,data):self.status_code=status;self.content=json.dumps(data).encode()
    def json(self):return json.loads(self.content)


@pytest.mark.parametrize('status,code',[(401,'MODEL_CONFIG'),(429,'MODEL_RATE_LIMIT'),(500,'MODEL_NETWORK')])
def test_tryon_provider_http_failures_do_not_retry(monkeypatch,tmp_path,status,code):
    monkeypatch.setattr(client,'ENV_PATH',tmp_path/'.env');monkeypatch.setenv('FASHN_API_KEY','test-only')
    calls=[]
    class Transport:
        def __init__(self,**kw):assert kw['timeout']<=20
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kw):calls.append(kw);return Response(status,{'message':'secret injected message'})
    monkeypatch.setattr(client,'_tryon_http_client',Transport)
    monkeypatch.setattr(client,'LOG_PATH',tmp_path/'calls.log')
    with pytest.raises(LLMError) as exc:client.tryon_submit(b'person',b'garment','tops')
    assert exc.value.code==code and len(calls)==1
    log=(tmp_path/'calls.log').read_text()
    assert 'test-only' not in log and 'secret injected' not in log
    assert calls[0]['json']['inputs']['return_base64'] is True


def test_tryon_key_checked_on_call_only(monkeypatch,tmp_path):
    monkeypatch.delenv('FASHN_API_KEY',raising=False);monkeypatch.setattr(client,'ENV_PATH',tmp_path/'.env')
    with pytest.raises(LLMError,match='FASHN_API_KEY'):client.tryon_configuration()
