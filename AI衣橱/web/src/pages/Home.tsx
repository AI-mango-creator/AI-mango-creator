import { useEffect, useState } from 'react';
import { loadWardrobe } from '../lib/api';
import { getProfile } from '../lib/profileApi';
import type { Page } from '../components/BottomNav';
import AppIcon, { weatherIcon } from '../components/AppIcon';
import type { IconName } from '../components/AppIcon';
import ExperiencePhoto from '../components/ExperiencePhoto';
import ProductDetail from './ProductDetail';
import {products,categoryNames} from '../lib/tryonApi';
import type {Product} from '../lib/tryonApi';
import type { WeatherState } from '../lib/weatherApi';
import { forecastIsFresh } from '../lib/weatherApi';
const shortcuts: { title: string; icon: IconName; page: Page; upload?: boolean }[] = [
  { title: '我的衣橱', icon: 'wardrobe', page: 'wardrobe' }, { title: '我的档案', icon: 'person', page: 'profile' },
  { title: '天气穿搭', icon: 'sun', page: 'weather' }, { title: 'AI搭配', icon: 'spark', page: 'outfits' },
];
export default function Home({ weather, onNavigate }: { weather: WeatherState; onNavigate: (p: Page, upload?: boolean) => void }) {
  const [items, setItems] = useState<Product[]>([]); const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [wardrobeCount,setWardrobeCount]=useState<number|null>(null);const [selected,setSelected]=useState<string|null>(()=>history.state?.experienceProduct??null);
  useEffect(()=>{const pop=(e:PopStateEvent)=>{setSelected(e.state?.experienceProduct??null);window.scrollTo(0,0);};window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop);},[]);
  function openProduct(id:string){history.pushState({experienceProduct:id},'');setSelected(id);window.scrollTo(0,0);}
  const [error, setError] = useState(''); const [revision, setRevision] = useState(0); const [summary, setSummary] = useState('完善我的资料'); const [group, setGroup] = useState('all');
  useEffect(() => { const c = new AbortController(); setState('loading');
    void loadWardrobe(c.signal, x => setWardrobeCount(x.length), () => setWardrobeCount(null));
    void products(c.signal).then(x=>{if(!c.signal.aborted){setItems(x);setState('ok');}}).catch(e=>{if(!c.signal.aborted){setError(e.message);setState('error');}});
    void getProfile(c.signal).then(p => { if (!c.signal.aborted) setSummary([p.height_cm ? p.height_cm + 'cm' : '', p.weight_kg ? p.weight_kg + 'kg' : ''].filter(Boolean).join(' · ') || '完善我的资料'); }).catch(() => {});
    return () => c.abort();
  }, [revision]);
  const day = weather.forecast && forecastIsFresh(weather.forecast) ? weather.forecast.days[0] : null;
  const visible = group === 'all' ? items : items.filter(x => x.category === group);
  if(selected)return <ProductDetail key={selected} productId={selected} onBack={()=>{if(history.state?.experienceProduct)history.back();else setSelected(null);}}/>;
  return <main className="home-page">
    <section className="home-top">
      <div className="home-intro"><span className="eyebrow">YOUR DAILY WARDROBE</span><span className="small-date">{new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date())}</span></div>
      <div className="home-summary"><button className="avatar-link" onClick={() => onNavigate('profile')}><span className="avatar-circle"><AppIcon name="person" /></span><span className="avatar-label">我的档案</span></button>
        <button className="closet-summary" onClick={() => onNavigate('wardrobe')}><strong>我的衣橱<span>（{wardrobeCount??'—'}件）</span></strong><small>{summary}</small></button>
        <button className="weather-mini" onClick={() => onNavigate('weather')}><AppIcon name={day ? weatherIcon(day.weather_code) : 'sun'} /><strong>{day ? `${Math.round(day.temp_min_c)}/${Math.round(day.temp_max_c)}°C` : weather.status === 'loading' ? '查询中' : '选择城市'}</strong><small>{day ? `${weather.city?.name} · ${day.weather_text}` : weather.status === 'error' ? '天气暂不可用' : '查看真实天气'}</small></button>
      </div>
      <div className="shortcut-grid">{shortcuts.map(x => <button key={x.title} onClick={() => onNavigate(x.page, x.upload)}><AppIcon name={x.icon} /><span>{x.title}</span></button>)}</div>
    </section>
    <section className="home-body"><button className="ai-hero" onClick={() => onNavigate('wardrobe')}><span><small>ONLY FROM YOUR CLOSET</small><strong><em>AI</em>帮我搭</strong><span className="hero-caption">把选择交给 AI，把今天留给自己</span><span className="hero-pill">开启今日搭配 <AppIcon name="arrow" /></span></span><span className="hero-art" aria-hidden="true"><span className="outfit-paper paper-one"><AppIcon name="wardrobe" /></span><span className="outfit-paper paper-two"><AppIcon name="spark" /></span><span className="outfit-paper paper-three"><AppIcon name="person" /></span></span></button>
      <div className="section-heading"><h1>服饰试穿体验</h1><span>体验素材 · 暂无平台合作</span></div>
      <nav aria-label="首页服饰分类" className="category-tabs">{Object.entries({all:'全部',...categoryNames}).map(([key,label])=><button key={key} aria-pressed={group===key} onClick={()=>setGroup(key)}>{label}</button>)}</nav>
      {state==='loading'&&<section role="status" className="home-feed"><div className="skeleton tall"/><div className="skeleton tall offset"/><p>正在读取体验服饰…</p></section>}
      {state==='error'&&<section className="panel" role="alert"><h2>体验服饰暂时无法加载</h2><p>{error}</p><button className="soft-button" onClick={()=>setRevision(x=>x+1)}>重新加载</button></section>}
      {state==='ok'&&visible.length===0&&<section className="empty-card"><AppIcon name="wardrobe"/><h2>{items.length?'这个分类暂无体验服饰':'体验服饰待准备'}</h2><p>此处仅展示有使用权的试穿素材。素材备妥后，即可选择服饰并体验AI试穿。</p><button className="soft-button" onClick={()=>onNavigate('wardrobe')}>查看我的衣橱</button></section>}
      {state==='ok'&&visible.length>0&&<section className="experience-grid" aria-label="体验服饰">{visible.map(item=><article className="experience-card" key={item.id}><button className="experience-cover" aria-label={'查看服饰：'+item.title} onClick={()=>openProduct(item.id)}><ExperiencePhoto id={item.id} alt={item.title}/><span className="experience-try">＋ AI试穿</span></button><div className="experience-copy"><h2><button onClick={()=>openProduct(item.id)}>{item.title}</button></h2><span className="post-tag">{categoryNames[item.category]}</span><small>{item.source_label}</small><p>体验素材</p></div></article>)}</section>}
    </section>
  </main>;
}
