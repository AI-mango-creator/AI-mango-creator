import { useEffect, useState } from 'react';
import My from './pages/My';
import {visitCheckin} from './lib/personalApi';
import Wardrobe from './pages/Wardrobe';
import Outfits from './pages/Outfits';
import Profile from './pages/Profile';
import Home from './pages/Home';
import Weather from './pages/Weather';
import Community from './pages/Community';
import BottomNav from './components/BottomNav';
import type { Page } from './components/BottomNav';
import { forecastTemperature, getWeather } from './lib/weatherApi';
import type { WeatherCity, WeatherSelection, WeatherState } from './lib/weatherApi';
export default function App() {
  useEffect(()=>{void visitCheckin();const focus=()=>{if(!document.hidden)void visitCheckin();};window.addEventListener('focus',focus);document.addEventListener('visibilitychange',focus);return()=>{window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus);};},[]);
  const [, clockTick] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => clockTick(x => x + 1), 30000); return () => clearInterval(timer); }, []);
  const [page, setPage] = useState<Page>('home'); const [revision, setRevision] = useState(0);
  const [city, setCity] = useState<WeatherCity | null>(null);
  const [weather, setWeather] = useState<WeatherState>({ city: null, forecast: null, status: 'empty', error: '', date: '' });
  const [selection, setSelection] = useState<WeatherSelection | null>(null);
  const [uploadEntry, setUploadEntry] = useState(false);
  useEffect(() => { if (!city) return; const c = new AbortController();
    setWeather({ city, forecast: null, status: 'loading', error: '', date: '' });
    void getWeather(city, c.signal).then(f => { if (!c.signal.aborted) setWeather({ city, forecast: f, status: 'ok', error: '', date: f.days[0].date }); }).catch(e => { if (!c.signal.aborted) setWeather({ city, forecast: null, status: 'error', error: e.message, date: '' }); });
    return () => c.abort();
  }, [city, revision]);
  function navigate(next: Page, upload = false, keepWeather = false) { void visitCheckin(); if (next === 'outfits' && !keepWeather) setSelection(null); setUploadEntry(upload); setPage(next); window.scrollTo(0, 0); }
  // 天气仅预填参数；用户点击生成后才调用模型。
  function useWeather() { if (!weather.forecast || !city) return;
    try { setSelection({ temperature: forecastTemperature(weather.forecast, weather.date), city: city.name, date: weather.date }); navigate('outfits', false, true); }
    catch (e) { setWeather({ ...weather, status: 'error', error: e instanceof Error ? e.message : '请刷新天气。' }); }
  }
  return <div className="app-frame" data-weather-temperature={selection?.temperature} data-upload-entry={uploadEntry}>
    {(page === 'wardrobe' || page === 'outfits') && <nav className="closet-subnav" aria-label="衣橱与搭配"><button aria-pressed={page==='wardrobe'} onClick={()=>navigate('wardrobe')}>我的衣橱</button><button aria-pressed={page==='outfits'} onClick={()=>navigate('outfits')}>AI搭配</button></nav>}
    {page === 'my' ? <My onArchive={()=>navigate('profile')} /> : page === 'community' ? <Community /> : page === 'home' ? <Home weather={weather} onNavigate={navigate} /> : page === 'weather' ? <Weather state={weather} onCity={setCity} onDate={date => setWeather(x => ({ ...x, date }))} onRefresh={() => setRevision(x => x + 1)} onUse={useWeather} onManual={() => { setSelection(null); navigate('outfits'); }} onBack={() => navigate('home')} /> : page === 'wardrobe' ? <Wardrobe initialUpload={uploadEntry} onAI={() => { setSelection(null); navigate('outfits'); }} /> : page === 'outfits' ? <Outfits initialWeather={selection} onBack={() => navigate('wardrobe')} /> : <Profile onBack={() => navigate('my')} />}
    <BottomNav page={page} onNavigate={next => { if (next === 'outfits') setSelection(null); navigate(next); }} />
  </div>;
}
