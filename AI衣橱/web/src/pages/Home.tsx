import { useEffect, useState } from 'react';
import { loadWardrobe } from '../lib/api';
import type { WardrobeItem } from '../lib/api';
import { getProfile } from '../lib/profileApi';
import type { Page } from '../components/BottomNav';
import AppIcon, { weatherIcon } from '../components/AppIcon';
import type { IconName } from '../components/AppIcon';
import ItemPhoto from '../components/ItemPhoto';
import type { WeatherState } from '../lib/weatherApi';
import { forecastIsFresh } from '../lib/weatherApi';
import { groupOf } from '../lib/wardrobeCategories';
const shortcuts: { title: string; icon: IconName; page: Page; upload?: boolean }[] = [
  { title: '我的衣橱', icon: 'wardrobe', page: 'wardrobe' }, { title: '身材档案', icon: 'person', page: 'profile' },
  { title: '天气穿搭', icon: 'sun', page: 'weather' }, { title: '上传衣物', icon: 'upload', page: 'wardrobe', upload: true }, { title: 'AI搭配', icon: 'spark', page: 'outfits' },
];
export default function Home({ weather, onNavigate }: { weather: WeatherState; onNavigate: (p: Page, upload?: boolean) => void }) {
  const [items, setItems] = useState<WardrobeItem[]>([]); const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [error, setError] = useState(''); const [revision, setRevision] = useState(0); const [summary, setSummary] = useState('完善我的资料'); const [group, setGroup] = useState('all');
  useEffect(() => { const c = new AbortController(); setState('loading');
    void loadWardrobe(c.signal, x => { setItems(x); setState('ok'); }, message => { setError(message); setState('error'); });
    void getProfile(c.signal).then(p => { if (!c.signal.aborted) setSummary([p.height_cm ? p.height_cm + 'cm' : '', p.weight_kg ? p.weight_kg + 'kg' : ''].filter(Boolean).join(' · ') || '完善我的资料'); }).catch(() => {});
    return () => c.abort();
  }, [revision]);
  const day = weather.forecast && forecastIsFresh(weather.forecast) ? weather.forecast.days[0] : null;
  const visible = group === 'all' ? items : items.filter(x => groupOf(x) === group);
  return <main className="home-page">
    <section className="home-top">
      <div className="home-intro"><span className="eyebrow">YOUR DAILY WARDROBE</span><span className="small-date">{new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date())}</span></div>
      <div className="home-summary"><button className="avatar-link" onClick={() => onNavigate('profile')}><span className="avatar-circle"><AppIcon name="person" /></span><span className="avatar-label">我的档案</span></button>
        <button className="closet-summary" onClick={() => onNavigate('wardrobe')}><strong>我的衣橱<span>（{state === 'ok' ? items.length : '—'}件）</span></strong><small>{summary}</small></button>
        <button className="weather-mini" onClick={() => onNavigate('weather')}><AppIcon name={day ? weatherIcon(day.weather_code) : 'sun'} /><strong>{day ? `${Math.round(day.temp_min_c)}/${Math.round(day.temp_max_c)}°C` : weather.status === 'loading' ? '查询中' : '选择城市'}</strong><small>{day ? `${weather.city?.name} · ${day.weather_text}` : weather.status === 'error' ? '天气暂不可用' : '查看真实天气'}</small></button>
      </div>
      <div className="shortcut-grid">{shortcuts.map(x => <button key={x.title} onClick={() => onNavigate(x.page, x.upload)}><AppIcon name={x.icon} /><span>{x.title}</span></button>)}</div>
    </section>
    <section className="home-body"><button className="ai-hero" onClick={() => onNavigate('wardrobe')}><span><small>ONLY FROM YOUR CLOSET</small><strong><em>AI</em>帮我搭</strong><span className="hero-caption">把选择交给 AI，把今天留给自己</span><span className="hero-pill">开启今日搭配 <AppIcon name="arrow" /></span></span><span className="hero-art" aria-hidden="true"><span className="outfit-paper paper-one"><AppIcon name="wardrobe" /></span><span className="outfit-paper paper-two"><AppIcon name="spark" /></span><span className="outfit-paper paper-three"><AppIcon name="person" /></span></span></button>
      <div className="section-heading"><h1>我的衣橱灵感</h1><span>来自你的每一件</span></div>
      <nav aria-label="首页衣物分类" className="category-tabs">{Object.entries({ all: '全部', tops: '上装', bottoms: '下装', skirts: '裙装', shoes: '鞋子' }).map(([key, label]) => <button key={key} aria-pressed={group === key} onClick={() => setGroup(key)}>{label}</button>)}</nav>
      {state === 'loading' && <section role="status" className="home-feed"><div className="skeleton tall" /><div className="skeleton tall offset" /><p>正在整理你的衣橱…</p></section>}
      {state === 'error' && <section className="panel" role="alert"><h2>衣橱暂时无法加载</h2><p>{error}</p><button className="soft-button" onClick={() => setRevision(x => x + 1)}>重新加载</button></section>}
      {state === 'ok' && visible.length === 0 && <section className="empty-card"><AppIcon name="wardrobe" /><h2>{items.length ? '这个分类还没有衣物' : '把你的第一件衣服放进来'}</h2><p>从一张照片开始，建立只属于你的穿搭灵感。</p><button className="gradient-button" onClick={() => onNavigate('wardrobe', true)}>上传衣物</button></section>}
      {state === 'ok' && visible.length > 0 && <section className="home-feed" aria-label="个人衣物灵感">{visible.map((item, i) => <button className={`inspiration-card ${i % 2 ? 'offset' : ''}`} key={item.id} onClick={() => onNavigate('wardrobe')}><ItemPhoto item={item} /><span className="feed-label">{item.needs_confirm ? '待确认' : '我的衣物'}</span><strong>{item.sub || item.name || '未命名单品'}</strong><small>{item.colors.join(' · ') || '等待你来完善'}</small></button>)}</section>}
    </section>
  </main>;
}
