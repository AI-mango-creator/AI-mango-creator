from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import HTTPException

from app.services.weather import forecast, search_cities


def payload():
    today = datetime.now(UTC).date()
    return {'timezone': 'UTC', 'daily': {
        'time': [(today + timedelta(days=i)).isoformat() for i in range(7)],
        'temperature_2m_min': [12.4] * 7, 'temperature_2m_max': [23.5] * 7,
        'weather_code': [0, 1, 3, 61, 95, 45, 71]}}


def test_forecast_seven_real_schema_days_and_fixed_request():
    def handle(request):
        assert request.url.host == 'api.open-meteo.com'
        assert request.url.params['forecast_days'] == '7'
        assert 'x-device-id' not in request.headers
        return httpx2.Response(200, json=payload())
    result = forecast(22.55, 114.1, transport=httpx2.MockTransport(handle))
    assert len(result.days) == 7
    assert result.provider == 'Open-Meteo'
    assert result.days[0].weather_text == '晴'
    assert result.days[3].weather_text == '小雨'
    assert '外套' in result.days[0].advice
    assert result.fetched_at.tzinfo is not None


def test_search_keeps_ambiguous_results_and_empty_is_valid():
    city = {'id': 1795565, 'name': '深圳', 'latitude': 22.55, 'longitude': 114.1,
            'country': '中国', 'admin1': '广东', 'timezone': 'Asia/Shanghai'}
    result = search_cities('深圳', transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json={'results': [city, city | {'id': 2}]})))
    assert [x.id for x in result.cities] == [1795565, 2]
    assert search_cities('不存在', transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json={}))).cities == []


@pytest.mark.parametrize('mode,status', [('timeout', 504), ('network', 502), ('http', 502), ('json', 502)])
def test_upstream_failures_are_chinese_and_never_retry(mode, status):
    calls = []
    def handle(request):
        calls.append(request)
        if mode == 'timeout':
            raise httpx2.ReadTimeout('private upstream detail')
        if mode == 'network':
            raise httpx2.ConnectError('private upstream detail')
        return httpx2.Response(429 if mode == 'http' else 200, content='not json')
    with pytest.raises(HTTPException) as exc:
        forecast(0, 0, transport=httpx2.MockTransport(handle))
    assert exc.value.status_code == status
    assert '天气' in exc.value.detail and 'private' not in exc.value.detail
    assert len(calls) == 1


@pytest.mark.parametrize('bad', ['short', 'nan', 'reversed', 'date', 'timezone', 'unknown_code'])
def test_invalid_provider_payload_rejected(bad):
    data = payload()
    if bad == 'short': data['daily']['weather_code'] = [0]
    if bad == 'nan': data['daily']['temperature_2m_min'][0] = None
    if bad == 'reversed': data['daily']['temperature_2m_min'][0] = 30
    if bad == 'date': data['daily']['time'][1] = data['daily']['time'][0]
    if bad == 'timezone': data['timezone'] = 'not-a-zone'
    if bad == 'unknown_code': data['daily']['weather_code'][0] = 999
    with pytest.raises(HTTPException) as exc:
        forecast(0, 0, transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json=data)))
    assert exc.value.status_code == 502


def test_upstream_has_total_deadline(monkeypatch):
    import asyncio

    from app.services import weather
    monkeypatch.setattr(weather, '_TOTAL_TIMEOUT', .01)
    async def slow(request):
        await asyncio.sleep(.08)
        return httpx2.Response(200, json=payload())
    with pytest.raises(HTTPException) as exc:
        forecast(0, 0, transport=httpx2.MockTransport(slow))
    assert exc.value.status_code == 504
