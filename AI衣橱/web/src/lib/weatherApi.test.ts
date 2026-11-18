import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { forecastIsFresh, forecastTemperature, getWeather, searchCities } from './weatherApi';
import type { WeatherForecast } from './weatherApi';

beforeEach(() => vi.stubGlobal('localStorage', { getItem: () => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', setItem() {} }));
afterEach(() => vi.unstubAllGlobals());
const now = new Date('2026-11-18T04:00:00Z');
const data: WeatherForecast = { provider: 'Open-Meteo', timezone: 'Asia/Shanghai', fetched_at: now.toISOString(),
  days: Array.from({ length: 7 }, (_, i) => ({ date: `2026-11-${18 + i}`, temp_min_c: -1.5 + i, temp_max_c: 20, weather_code: 0, weather_text: '晴', advice: '早晚偏凉' })) };

it('城市搜索经自身后端，带设备头与取消信号', async () => {
  const city = { id: 1, name: '深圳', admin1: '广东', country: '中国', latitude: 22.55, longitude: 114.1, timezone: 'Asia/Shanghai' };
  const control = new AbortController();
  expect(await searchCities('深圳', control.signal, async (url, options) => {
    expect(String(url)).toContain('/api/weather/cities?q=');
    expect(new Headers(options?.headers).get('X-Device-ID')).toContain('aaaaaaaa');
    expect(options?.signal).toBeDefined();
    return Response.json({ cities: [city] });
  })).toEqual([city]);
});
it('城市空结果合法，非法查询和坐标不发请求', async () => {
  expect(await searchCities('未知', undefined, async () => Response.json({ cities: [] }))).toEqual([]);
  const noFetch = vi.fn();
  await expect(searchCities('x', undefined, noFetch)).rejects.toThrow();
  await expect(getWeather({ latitude: Infinity, longitude: 0 }, undefined, noFetch)).rejects.toThrow();
  expect(noFetch).not.toHaveBeenCalled();
});
it('七天字段完整才能展示，保留中文错误', async () => {
  expect(await getWeather({ latitude: 0, longitude: 0 }, undefined, async () => Response.json(data))).toEqual(data);
  await expect(getWeather({ latitude: 0, longitude: 0 }, undefined, async () => Response.json({ ...data, days: data.days.slice(1) }))).rejects.toThrow('天气');
  await expect(searchCities('深圳', undefined, async () => Response.json({ detail: '天气服务等待超时' }, { status: 504 }))).rejects.toThrow('天气服务等待超时');
});
it('所选日期最低温四舍五入，负数与手动温度一致', () => {
  expect(forecastTemperature(data, '2026-11-18', now)).toBe(-1);
  expect(forecastTemperature(data, '2026-11-20', now)).toBe(1);
  expect(() => forecastTemperature(data, '2026-11-30', now)).toThrow();
});
it('按城市时区判断过期，跨日与未来时间不预填旧天气', () => {
  expect(forecastIsFresh(data, now)).toBe(true);
  expect(forecastIsFresh(data, new Date('2026-11-18T16:01:00Z'))).toBe(false);
  expect(forecastIsFresh({ ...data, fetched_at: '2026-11-19T04:00:00Z' }, now)).toBe(false);
  expect(() => forecastTemperature(data, data.days[0].date, new Date('2026-11-19T04:00:00Z'))).toThrow('刷新');
});
it('中止保留取消语义，不伪报网络失败', async () => {
  const controller = new AbortController(); controller.abort();
  await expect(searchCities('深圳', controller.signal, async () => { throw new DOMException('Aborted', 'AbortError'); })).rejects.toMatchObject({ name: 'AbortError' });
});
