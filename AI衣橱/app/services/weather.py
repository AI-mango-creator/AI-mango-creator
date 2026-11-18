"""城市及预报只从固定天气域名读取；不访问LLM、衣柜或设备资料。"""
import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx2
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import WeatherCities, WeatherCity, WeatherDay, WeatherForecast
from app.services.filter import temperature_band

_http_client = httpx2.AsyncClient
_TOTAL_TIMEOUT = 8
_CODES = {0: '晴', 1: '晴间多云', 2: '局部多云', 3: '阴', 45: '雾', 48: '冻雾',
          51: '小毛毛雨', 53: '毛毛雨', 55: '强毛毛雨', 56: '冻毛毛雨', 57: '强冻毛毛雨',
          61: '小雨', 63: '中雨', 65: '大雨', 66: '冻雨', 67: '强冻雨',
          71: '小雪', 73: '中雪', 75: '大雪', 77: '雪粒', 80: '小阵雨', 81: '阵雨',
          82: '强阵雨', 85: '阵雪', 86: '强阵雪', 95: '雷雨', 96: '雷雨伴冰雹', 99: '强雷雨伴冰雹'}
_ADVICE = {'cold': '气温偏冷，搭配时需要外套，优先选择较厚的衣物。',
           'cool': '早晚偏凉，搭配时需要外套，注意温差。',
           'warm': '气温温暖，优先选择轻薄衣物，基础搭配不含外套。',
           'hot': '气温较热，优先选择清凉衣物，基础搭配不含外套。'}


class _Cities(BaseModel):
    results: list[WeatherCity] = Field(default_factory=list, max_length=5)


class _Daily(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    time: list[str] = Field(min_length=7, max_length=7)
    temperature_2m_min: list[float] = Field(min_length=7, max_length=7)
    temperature_2m_max: list[float] = Field(min_length=7, max_length=7)
    weather_code: list[int] = Field(min_length=7, max_length=7)


class _Forecast(BaseModel):
    timezone: str
    daily: _Daily


def _get(url, params, transport):
    async def fetch():
        async with asyncio.timeout(_TOTAL_TIMEOUT):
            options = {'timeout': 8, 'follow_redirects': False}
            if transport is not None:
                options['transport'] = transport
            async with _http_client(**options) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.content
    try:
        # 路由为同步函数，在FastAPI线程池执行；总deadline涵盖连接、读完整响应和关闭。
        return asyncio.run(fetch())
    except (httpx2.TimeoutException, TimeoutError):
        raise HTTPException(504, '天气服务等待超时，请重试或手动输入温度。') from None
    except httpx2.HTTPError:
        raise HTTPException(502, '天气服务暂时无法连接，请重试或手动输入温度。') from None


def search_cities(q: str, *, transport=None) -> WeatherCities:
    raw = _get('https://geocoding-api.open-meteo.com/v1/search',
               {'name': q, 'language': 'zh', 'count': 5, 'format': 'json'}, transport)
    try:
        cities = _Cities.model_validate_json(raw).results
        for city in cities:
            ZoneInfo(city.timezone)
        return WeatherCities(cities=cities)
    except (ValidationError, ZoneInfoNotFoundError, ValueError):
        raise HTTPException(502, '天气城市响应有误，请稍后重试。') from None


def forecast(latitude: float, longitude: float, *, transport=None) -> WeatherForecast:
    raw = _get('https://api.open-meteo.com/v1/forecast',
               {'latitude': latitude, 'longitude': longitude, 'timezone': 'auto', 'forecast_days': 7,
                'daily': 'weather_code,temperature_2m_min,temperature_2m_max'}, transport)
    try:
        data = _Forecast.model_validate_json(raw)
        today = datetime.now(ZoneInfo(data.timezone)).date()
        expected = [(today + timedelta(days=i)).isoformat() for i in range(7)]
        if data.daily.time != expected:
            raise ValueError('预报日期不完整或过期')
        days = []
        for date, low, high, code in zip(data.daily.time, data.daily.temperature_2m_min,
                                        data.daily.temperature_2m_max, data.daily.weather_code):
            days.append(WeatherDay(date=date, temp_min_c=low, temp_max_c=high, weather_code=code,
                                   weather_text=_CODES[code], advice=_ADVICE[temperature_band(int(low // 1 + (low % 1 >= .5)))]))
        return WeatherForecast(timezone=data.timezone, fetched_at=datetime.now(UTC), days=days)
    except (ValidationError, ZoneInfoNotFoundError, ValueError, KeyError):
        raise HTTPException(502, '天气预报数据不完整或已过期，请重试或手动输入温度。') from None
