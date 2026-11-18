import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import BodyShapeGuide from '../components/BodyShapeGuide';
import { getProfile, parseProfileDraft, saveProfile } from '../lib/profileApi';
import type { ProfileDraft } from '../lib/profileApi';

export default function Profile() {
  const [draft, setDraft] = useState<ProfileDraft>({ height: '', weight: '', shape: '' });
  const [status, setStatus] = useState<'loading' | 'error' | 'ok'>('loading');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [owner, setOwner] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setStatus('loading'); setError('');
    void getProfile(controller.signal).then(profile => {
      if (!controller.signal.aborted) { setDraft({ height: profile.height_cm?.toString() ?? '', weight: profile.weight_kg?.toString() ?? '', shape: profile.body_shape ?? '' }); setOwner(profile.owner_id); setStatus('ok'); }
    }).catch(failure => { if (!controller.signal.aborted) { setError(failure.message); setStatus('error'); } });
    return () => controller.abort();
  }, [revision]);
  async function save(event: FormEvent) {
    event.preventDefault(); setError(''); setNotice('');
    try {
      const input = parseProfileDraft(draft); setSaving(true);
      await saveProfile(input, undefined, owner); setNotice('资料已保存，下次打开仍会保留。');
    } catch (failure) { setError(failure instanceof Error ? failure.message : '保存失败，请重试。'); }
    finally { setSaving(false); }
  }
  return <main className="shell">
    <header className="mb-6"><p className="text-xs tracking-widest text-slate-500">WARDROBE COPILOT</p><h1 className="mt-3 text-3xl font-semibold">我的身材资料</h1><p className="mt-3 text-sm leading-6 text-slate-600">由你填写和选择，可留空或随时修改。</p></header>
    {status === 'loading' && <section className="panel" role="status">正在读取身材资料…<div className="mt-4 h-12 animate-pulse rounded-xl bg-slate-200" /></section>}
    {status === 'error' && <section className="panel" role="alert"><p>{error}</p><button className="mt-4 rounded-xl bg-slate-800 px-4 py-3 text-white" onClick={() => setRevision(x => x + 1)}>重新加载</button></section>}
    {status === 'ok' && <form className="panel min-w-0" onSubmit={save}>
      {!draft.height && !draft.weight && !draft.shape && <p className="mb-4 text-sm text-slate-600">还没有填写资料，可以从下面开始；也可直接使用基础搭配。</p>}
      <fieldset disabled={saving} className="min-w-0">
        <div className="mb-6 grid min-w-0 grid-cols-2 gap-3">
          <label className="min-w-0 text-sm">身高（cm）<input type="number" inputMode="decimal" step="any" min="0" value={draft.height} onChange={e => setDraft({ ...draft, height: e.target.value })} className="mt-2 w-full min-w-0 rounded-xl border border-slate-300 bg-white p-3" placeholder="例如 165" /></label>
          <label className="min-w-0 text-sm">体重（kg）<input type="number" inputMode="decimal" step="any" min="0" value={draft.weight} onChange={e => setDraft({ ...draft, weight: e.target.value })} className="mt-2 w-full min-w-0 rounded-xl border border-slate-300 bg-white p-3" placeholder="例如 55.5" /></label>
        </div>
        <BodyShapeGuide value={draft.shape} onChange={shape => setDraft({ ...draft, shape })} disabled={saving} />
        <p className="mt-5 text-xs leading-5 text-slate-500">填写后，生成搭配时资料会发送给现有模型服务，供说明参考；不用于硬性筛选，不保证尺码或合身效果。未填写不影响基础搭配。</p>
        {error && <div role="alert" className="mt-4 text-sm text-red-900"><p>{error}</p><button type="button" className="mt-2 underline" onClick={() => setRevision(x => x + 1)}>重新加载资料</button></div>}
        {notice && <p role="status" className="mt-4 text-sm text-green-800">{notice}</p>}
        <button type="submit" className="mt-5 w-full rounded-xl bg-slate-800 px-4 py-3 text-white disabled:opacity-50">{saving ? '正在保存…' : '保存资料'}</button>
      </fieldset>
    </form>}
  </main>;
}
