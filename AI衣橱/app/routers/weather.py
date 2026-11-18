from typing import Annotated

from fastapi import APIRouter, Query

from app.models import WeatherCities, WeatherForecast
from app.services.weather import forecast, search_cities

router = APIRouter(prefix='/api/weather', tags=['真实城市天气'])


@router.get('/cities', response_model=WeatherCities)
def cities(q: Annotated[str, Query(min_length=2, max_length=50, pattern=r'^\S(?:.*\S)?$')]):
    return search_cities(q)


@router.get('', response_model=WeatherForecast)
def weather(latitude: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
            longitude: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]):
    return forecast(latitude, longitude)
