import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import BodyShapeGuide, { bodyShapes } from '../components/BodyShapeGuide';
import AppIcon from '../components/AppIcon';
import { getProfile, parseProfileDraft, saveProfile } from '../lib/profileApi';
import type { ProfileDraft } from '../lib/profileApi';

export default function Profile({ onBack }: { onBack?: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ProfileDraft>({ height: '', weight: '', shape: '' });
  const [saved, setSaved] = useState<ProfileDraft>({ height: '', weight: '', shape: '' });
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
      if (!controller.signal.aborted) { setDraft({ height: profile.height_cm?.toString() ?? '', weight: profile.weight_kg?.toString() ?? '', shape: profile.body_shape ?? '' }); setSaved({ height: profile.height_cm?.toString() ?? '', weight: profile.weight_kg?.toString() ?? '', shape: profile.body_shape ?? '' }); setOwner(profile.owner_id); setStatus('ok'); }
    }).catch(failure => { if (!controller.signal.aborted) { setError(failure.message); setStatus('error'); } });
    return () => controller.abort();
  }, [revision]);
  async function save(event: FormEvent) {
    event.preventDefault(); setError(''); setNotice('');
    try {
      const input = parseProfileDraft(draft); setSaving(true);
      const updated = await saveProfile(input, undefined, owner); setSaved({ height: updated.height_cm?.toString() ?? '', weight: updated.weight_kg?.toString() ?? '', shape: updated.body_shape ?? '' }); setNotice('资料已保存，下次打开仍会保留。'); setEditing(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : '保存失败，请重试。'); }
    finally { setSaving(false); }
  }
  return <main className="shell profile-page">
    <header className="detail-header"><button aria-label="返回首页" onClick={onBack}><AppIcon name="back" /></button><h1>我的档案</h1><span /></header>
    {notice && !editing && <p role="status" className="notice-box">{notice}</p>}
    {status === 'ok' && !editing && <>
      <section className="profile-identity panel"><h2><AppIcon name="person" />我的资料</h2><div className="identity-preview"><AppIcon name="person" /><span>个人档案</span></div><p className="muted">每一种身材，都有自己的穿搭答案。</p><button className="profile-edit" onClick={() => { setDraft({ ...saved }); setEditing(true); }}><AppIcon name="edit" />完善我的档案</button></section>
      <section className="profile-overview panel"><h2><AppIcon name="person" />我的身型</h2><h3>我的体型</h3><p>{[saved.height ? saved.height + 'cm' : '身高未填写', saved.weight ? saved.weight + 'kg' : '体重未填写', bodyShapes.find(x => x.id === saved.shape)?.name.split('｜')[1] ?? '体型未选择'].join('｜')}</p><h3>体型画像</h3><p>{bodyShapes.find(x => x.id === saved.shape)?.description ?? '了解自己的比例，让每次选择更轻松。'}</p><button className="profile-edit" onClick={() => { setDraft({ ...saved }); setEditing(true); }}><AppIcon name="edit" />编辑</button></section>
      <p className="profile-note">由你填写，可随时修改。仅供搭配说明参考，不保证尺码或合身效果。</p>
    </>}
    {status === 'loading' && <section className="panel" role="status">正在读取身材资料…<div className="mt-4 h-12 animate-pulse rounded-xl bg-slate-200" /></section>}
    {status === 'error' && <section className="panel" role="alert"><p>{error}</p><button className="mt-4 rounded-xl bg-slate-800 px-4 py-3 text-white" onClick={() => setRevision(x => x + 1)}>重新加载</button></section>}
    {status === 'ok' && editing && <form className="panel min-w-0" onSubmit={save}>
      {!draft.height && !draft.weight && !draft.shape && <p className="mb-4 text-sm text-slate-600">还没有填写资料，可以从下面开始；也可直接使用基础搭配。</p>}
      <fieldset disabled={saving} className="min-w-0">
        <div className="mb-6 grid min-w-0 grid-cols-2 gap-3">
          <label className="min-w-0 text-sm">身高（cm）<input type="number" inputMode="decimal" step="any" min="0" value={draft.height} onChange={e => setDraft({ ...draft, height: e.target.value })} className="mt-2 w-full min-w-0 rounded-xl border border-slate-300 bg-white p-3" placeholder="例如 165" /></label>
          <label className="min-w-0 text-sm">体重（kg）<input type="number" inputMode="decimal" step="any" min="0" value={draft.weight} onChange={e => setDraft({ ...draft, weight: e.target.value })} className="mt-2 w-full min-w-0 rounded-xl border border-slate-300 bg-white p-3" placeholder="例如 55.5" /></label>
        </div>
        <h2 className="mb-5 text-xl font-semibold">编辑我的身型</h2>
        <BodyShapeGuide value={draft.shape} onChange={shape => setDraft({ ...draft, shape })} disabled={saving} />
        <p className="mt-5 text-xs leading-5 text-slate-500">填写后，生成搭配时资料会发送给现有模型服务，供说明参考；不用于硬性筛选，不保证尺码或合身效果。未填写不影响基础搭配。</p>
        {error && <div role="alert" className="mt-4 text-sm text-red-900"><p>{error}</p><button type="button" className="mt-2 underline" onClick={() => setRevision(x => x + 1)}>重新加载资料</button></div>}
        {notice && <p role="status" className="mt-4 text-sm text-green-800">{notice}</p>}
        <button type="submit" className="mt-5 w-full rounded-xl bg-slate-800 px-4 py-3 text-white disabled:opacity-50">{saving ? '正在保存…' : '保存资料'}</button>
        <button type="button" className="mt-3 w-full py-3 text-sm text-slate-500" onClick={() => setEditing(false)}>返回档案</button>
      </fieldset>
    </form>}
  </main>;
}
