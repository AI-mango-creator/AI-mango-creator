import httpx2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import weather
from app.tests.test_weather import payload

OWNER = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


def test_weather_routes_and_owner_guard(monkeypatch):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx2.Response(200, json=payload() if request.url.host == 'api.open-meteo.com' else {})
    original = httpx2.AsyncClient
    monkeypatch.setattr(weather, '_http_client', lambda **kw: original(**kw, transport=httpx2.MockTransport(handle)))
    with TestClient(app, headers={'X-Device-ID': OWNER}) as c:
        assert c.get('/api/weather/cities?q=深圳').json() == {'cities': []}
        response = c.get('/api/weather?latitude=22.55&longitude=114.1')
        assert response.status_code == 200
        assert len(response.json()['days']) == 7
        assert response.headers['cache-control'] == 'no-store'
        assert c.get('/api/weather?latitude=0&longitude=0', headers={'X-Device-ID': ''}).status_code == 400
        assert len(requests) == 2


@pytest.mark.parametrize('query', ['latitude=nan&longitude=0', 'latitude=91&longitude=0',
                                  'latitude=0&longitude=181', 'latitude=0', 'latitude=inf&longitude=0'])
def test_weather_bad_coordinates_never_call_provider(query, monkeypatch):
    monkeypatch.setattr(weather, '_http_client', lambda **kw: pytest.fail('must not call network'))
    with TestClient(app, headers={'X-Device-ID': OWNER}) as c:
        assert c.get('/api/weather?' + query).status_code == 400


@pytest.mark.parametrize('q', ['', 'x', 'x' * 51, '  '])
def test_bad_city_query(q):
    with TestClient(app, headers={'X-Device-ID': OWNER}) as c:
        assert c.get('/api/weather/cities', params={'q': q}).status_code == 400
