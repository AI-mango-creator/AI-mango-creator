import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import AppIcon, { weatherIcon } from '../components/AppIcon';
import { forecastIsFresh, searchCities } from '../lib/weatherApi';
import type { WeatherCity, WeatherState } from '../lib/weatherApi';
export default function Weather({ state, onCity, onDate, onRefresh, onUse, onManual, onBack }: {
  state: WeatherState; onCity: (city: WeatherCity) => void; onDate: (date: string) => void;
  onRefresh: () => void; onUse: () => void; onManual: () => void; onBack: () => void;
}) {
  const [query, setQuery] = useState(''); const [cities, setCities] = useState<WeatherCity[]>([]);
  const [search, setSearch] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle'); const [error, setError] = useState(''); const [showSearch, setShowSearch] = useState(!state.city);
  const request = useRef<AbortController | null>(null);
  const [, tick] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => tick(x => x + 1), 30000); return () => { clearInterval(timer); request.current?.abort(); }; }, []);
  async function find(event: FormEvent) { event.preventDefault(); request.current?.abort(); const c = new AbortController(); request.current = c; setSearch('loading'); setError('');
    try { const result = await searchCities(query, c.signal); if (!c.signal.aborted) { setCities(result); setSearch('ok'); } }
    catch (failure) { if (!c.signal.aborted) { setSearch('error'); setError(failure instanceof Error ? failure.message : '城市查询失败，请重试。'); } }
  }
  const fresh = state.forecast && forecastIsFresh(state.forecast); const day = state.forecast?.days.find(x => x.date === state.date) ?? state.forecast?.days[0];
  return <main className="shell weather-page">
    <header className="detail-header"><button aria-label="返回首页" onClick={onBack}><AppIcon name="back" /></button><h1>每日穿搭</h1><span /></header>
    <button className="city-switch" onClick={() => setShowSearch(x => !x)}><span>⌖ {state.city ? `${state.city.name} · ${state.city.admin1}` : '选择你的城市'}</span><span>切换 ›</span></button>
    {showSearch && <section className="panel city-panel"><h2>查找城市</h2><form onSubmit={find} className="city-search"><input aria-label="城市名称" value={query} onChange={e => { request.current?.abort(); setQuery(e.target.value); setSearch('idle'); setCities([]); }} placeholder="例如 深圳、杭州" maxLength={50} /><button type="submit" className="gradient-button" disabled={search === 'loading'}>{search === 'loading' ? '查询中…' : '搜索'}</button></form>
      <p className="muted">选择城市即可查询，无需定位权限。</p>
      {search === 'loading' && <p role="status">正在查询城市…</p>}{search === 'error' && <p role="alert" className="error-text">{error}</p>}
      {search === 'ok' && cities.length === 0 && <p>没有找到该城市，请尝试完整名称或拼音。</p>}
      {cities.length > 0 && <ul className="city-results">{cities.map(city => <li key={city.id}><button onClick={() => { onCity(city); setShowSearch(false); }}><strong>{city.name}</strong><small>{[city.admin1, city.country].filter(Boolean).join(' · ')}</small><AppIcon name="arrow" /></button></li>)}</ul>}
    </section>}
    {state.status === 'empty' && <section className="empty-card"><AppIcon name="sun" /><h2>看看你所在城市的天气</h2><p>搜索并选择城市后，这里会展示真实七天预报。</p><button className="soft-button" onClick={onManual}>也可以手动输入温度搭配</button></section>}
    {state.status === 'loading' && <section role="status" className="panel"><div className="skeleton weather-skeleton" /><p>正在获取真实天气预报…</p></section>}
    {state.status === 'error' && <section className="panel" role="alert"><h2>天气暂时无法获取</h2><p className="error-text">{state.error}</p><div className="button-row"><button className="gradient-button" onClick={onRefresh}>重新获取</button><button className="soft-button" onClick={onManual}>手动输入温度</button></div></section>}
    {state.status === 'ok' && state.forecast && day && <>
      <nav className="weather-dates" aria-label="七天预报日期">{state.forecast.days.map((d, i) => <button key={d.date} aria-pressed={d.date === day.date} onClick={() => onDate(d.date)}><span>{i === 0 ? '今天' : new Intl.DateTimeFormat('zh-CN', { weekday: 'short', timeZone: 'UTC' }).format(new Date(d.date + 'T12:00:00Z'))}</span><strong>{Number(d.date.slice(-2))}</strong><AppIcon name={weatherIcon(d.weather_code)} /></button>)}</nav>
      <section className="forecast-card"><div className="forecast-top"><div><strong>{Math.round(day.temp_min_c)}/{Math.round(day.temp_max_c)}<span>°C</span></strong><p>{day.weather_text}</p></div><AppIcon name={weatherIcon(day.weather_code)} /></div><div className="forecast-city">⌖ {state.city?.name}<span>{day.date}</span></div><div className="advice"><h2>当日穿搭建议</h2><p>{day.advice}</p></div><p className="muted">天气预报仅供参考，以所选日期最低温搭配。</p></section>
      {!fresh && <p role="alert" className="error-text">天气已过期，请重新获取后再带入搭配。<button className="text-link" onClick={onRefresh}>刷新天气</button></p>}
      <section className="weather-cta"><span className="eyebrow">DRESS FOR THE DAY</span><h2>让天气，成为穿搭的灵感</h2><p>从自己的衣橱里，找到今天的答案。</p><button className="gradient-button" disabled={!fresh} onClick={onUse}>用 {Math.round(day.temp_min_c)}°C 帮我搭</button><button className="soft-button" onClick={onManual}>自行设置温度与场合</button></section>
      <p className="weather-credit">预报来源 <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · 获取于 {new Date(state.forecast.fetched_at).toLocaleString('zh-CN')}<br />城市仅本次保留，刷新后重新选择。</p>
    </>}
  </main>;
}
