import { deviceHeaders } from './deviceId';
export type WeatherCity = { id: number; name: string; admin1: string; country: string; latitude: number; longitude: number; timezone: string };
export type WeatherDay = { date: string; temp_min_c: number; temp_max_c: number; weather_code: number; weather_text: string; advice: string };
export type WeatherForecast = { provider: 'Open-Meteo'; timezone: string; fetched_at: string; days: WeatherDay[] };
export type WeatherSelection = { temperature: number; city: string; date: string };
export type WeatherState = { city: WeatherCity | null; forecast: WeatherForecast | null; status: 'empty' | 'loading' | 'ok' | 'error'; error: string; date: string };

async function request(path: string, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<unknown> {
  const timeout = AbortSignal.timeout(12000);
  let response: Response;
  try { response = await fetcher(path, { headers: deviceHeaders(), signal: signal ? AbortSignal.any([signal, timeout]) : timeout }); }
  catch (error) { if (signal?.aborted) throw error; throw new Error('天气连接失败，请重试或手动输入温度。'); }
  let payload: unknown;
  try { payload = await response.json(); } catch { throw new Error('天气响应格式有误，请重试。'); }
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : null;
    throw new Error(typeof message === 'string' && /[\u4e00-\u9fff]/.test(message) ? message : '天气暂不可用，请稍后重试。');
  }
  return payload;
}
const record = (x: unknown): x is Record<string, unknown> => Boolean(x && typeof x === 'object');
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
function zoneDate(timezone: string, now: Date) { return new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now); }
export function forecastIsFresh(data: WeatherForecast, now = new Date()): boolean {
  try { return data.days[0]?.date === zoneDate(data.timezone, now) && Number.isFinite(Date.parse(data.fetched_at)) && Date.parse(data.fetched_at) <= now.getTime() + 60000 && now.getTime() - Date.parse(data.fetched_at) < 3600000; }
  catch { return false; }
}
export function forecastTemperature(data: WeatherForecast, date: string, now = new Date()): number {
  if (!forecastIsFresh(data, now)) throw new Error('天气已过期，请刷新后再搭配。');
  const day = data.days.find(x => x.date === date);
  if (!day) throw new Error('请选择有效的预报日期。');
  return Math.round(day.temp_min_c);
}
export async function searchCities(q: string, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<WeatherCity[]> {
  q = q.trim(); if (q.length < 2 || q.length > 50) throw new Error('请输入2至50个字的城市名称。');
  const data = await request('/api/weather/cities?q=' + encodeURIComponent(q), signal, fetcher);
  if (!record(data) || !Array.isArray(data.cities) || data.cities.length > 5 || data.cities.some(c => !record(c) || !Number.isInteger(c.id) || Number(c.id) <= 0 || typeof c.name !== 'string' || !c.name || !finite(c.latitude) || Math.abs(c.latitude) > 90 || !finite(c.longitude) || Math.abs(c.longitude) > 180 || typeof c.timezone !== 'string' || typeof c.admin1 !== 'string' || typeof c.country !== 'string')) throw new Error('天气城市字段有误，请重试。');
  return data.cities as WeatherCity[];
}
export async function getWeather(city: Pick<WeatherCity, 'latitude' | 'longitude'>, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<WeatherForecast> {
  if (!finite(city.latitude) || Math.abs(city.latitude) > 90 || !finite(city.longitude) || Math.abs(city.longitude) > 180) throw new Error('城市坐标无效，请重新选择。');
  const data = await request(`/api/weather?latitude=${city.latitude}&longitude=${city.longitude}`, signal, fetcher);
  if (!record(data) || data.provider !== 'Open-Meteo' || typeof data.timezone !== 'string' || typeof data.fetched_at !== 'string' || !Array.isArray(data.days) || data.days.length !== 7 || data.days.some(d => !record(d) || typeof d.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(d.date) || !finite(d.temp_min_c) || d.temp_min_c < -100 || !finite(d.temp_max_c) || d.temp_max_c > 70 || d.temp_min_c > d.temp_max_c || !Number.isInteger(d.weather_code) || typeof d.weather_text !== 'string' || typeof d.advice !== 'string')) throw new Error('天气预报字段不完整，请刷新重试。');
  const result = data as WeatherForecast;
  if (result.days.some((d, i) => i > 0 && Date.parse(d.date) - Date.parse(result.days[i - 1].date) !== 86400000)) throw new Error('天气预报日期有误，请刷新重试。');
  return result;
}
