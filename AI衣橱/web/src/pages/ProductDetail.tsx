import {useEffect,useRef,useState} from 'react';
import {getHistoricalTryon} from '../lib/personalApi';
import AppIcon from '../components/AppIcon';
import ExperiencePhoto from '../components/ExperiencePhoto';
import {getDeviceId} from '../lib/deviceId';
import {categoryNames,deleteTryon,getProduct,getTryon,recentTryons,TryonApiError,TryonAttempt} from '../lib/tryonApi';
import type {Product,Tryon} from '../lib/tryonApi';
import {canShowResult,getTryonView} from '../lib/tryonView';
export default function ProductDetail({productId,initialTaskId,onBack}:{productId:string;initialTaskId?:string;onBack:()=>void}){
 const [product,setProduct]=useState<Product|null>(null),[status,setStatus]=useState<'loading'|'ok'|'error'>('loading'),[error,setError]=useState(''),[revision,setRevision]=useState(0),[photo,setPhoto]=useState<File|null>(null),[preview,setPreview]=useState(''),[consent,setConsent]=useState(false),[job,setJob]=useState<Tryon|null>(null),[busy,setBusy]=useState(false),[result,setResult]=useState(true),[confirmNew,setConfirmNew]=useState(false),[renew,setRenew]=useState(false),[confirmDelete,setConfirmDelete]=useState(false);
 const owner=useRef(getDeviceId()),ticket=useRef<TryonAttempt|null>(null),request=useRef<AbortController|null>(null),alive=useRef(true);
 useEffect(()=>{alive.current=true;const c=new AbortController();setStatus('loading');setError('');setJob(null);
 const selected=initialTaskId?getHistoricalTryon(initialTaskId,c.signal).then(x=>{if(x.product_id!==productId)throw new Error('这条历史记录与服饰不匹配，请返回重新打开。');return x;}):recentTryons(productId,c.signal).then(x=>x[0]??null);
 void Promise.all([getProduct(productId,c.signal),selected]).then(([p,j])=>{if(!c.signal.aborted){setProduct(p);setJob(j);setStatus('ok');}}).catch(e=>{if(!c.signal.aborted){setStatus('error');setError(e.message);}});return()=>{alive.current=false;c.abort();request.current?.abort();};},[productId,initialTaskId,revision]);
 useEffect(()=>{if(!photo){setPreview('');return;}const url=URL.createObjectURL(photo);setPreview(url);return()=>URL.revokeObjectURL(url);},[photo]);
 useEffect(()=>{if(!job||job.id===initialTaskId||!getTryonView(job.status).busy)return;const c=new AbortController();let timer:ReturnType<typeof setTimeout>;async function poll(){try{const next=await getTryon(job!.id,c.signal);if(!c.signal.aborted){setJob(next);setError('');}}catch(e){if(!c.signal.aborted)setError(e instanceof Error?e.message:'查询失败，请重试。');}}timer=setTimeout(poll,2000);return()=>{clearTimeout(timer);c.abort();};},[job]);
 function checkOwner(){if(owner.current!==getDeviceId())throw new Error('设备已变化，请返回首页重新打开。');}
 async function submit(fresh=false){if(busy||!photo||!consent)return;setBusy(true);setError('');if(fresh){ticket.current=null;setJob(null);setConfirmNew(false);setRenew(false);}const c=new AbortController();request.current=c;
 try{checkOwner();if(!ticket.current)ticket.current=new TryonAttempt(productId,owner.current);const next=await ticket.current.submit(photo,consent,c.signal);if(alive.current&&!c.signal.aborted){setJob(next);setResult(true);setRenew(false);setConfirmNew(false);}}
 catch(e){if(alive.current&&!c.signal.aborted){setError(e instanceof Error?e.message:'试穿失败，照片仍保留。');if(e instanceof TryonApiError&&[409,410].includes(e.status))setRenew(true);}}
 finally{if(alive.current&&!c.signal.aborted)setBusy(false);}}
 async function refresh(){if(!job)return;setBusy(true);try{checkOwner();const next=job.id===initialTaskId?await getHistoricalTryon(job.id):await getTryon(job.id);if(alive.current){setJob(next);setError('');}}catch(e){if(alive.current)setError(e instanceof Error?e.message:'查询失败。');}finally{if(alive.current)setBusy(false);}}
 async function remove(){if(!job)return;setBusy(true);try{checkOwner();await deleteTryon(job.id);if(alive.current){setJob(null);ticket.current=null;setConfirmDelete(false);setError('');}}catch(e){if(alive.current)setError(e instanceof Error?e.message:'删除失败。');}finally{if(alive.current)setBusy(false);}}
 const view=job?getTryonView(job.status):null;const working=busy||!!view?.busy;
 return <main className="product-detail"><header className="product-header"><button aria-label="返回首页" onClick={onBack}><AppIcon name="back"/></button><h1>服饰详情</h1><span/></header>
 {status==='loading'&&<section role="status" className="panel"><div className="skeleton tall"/><p>正在读取体验服饰…</p></section>}
 {status==='error'&&<section className="empty-card" role="alert"><h2>服饰暂时无法加载</h2><p>{error}</p><button className="soft-button" onClick={()=>setRevision(x=>x+1)}>重新加载</button></section>}
 {status==='ok'&&product&&<><section className="product-hero">{job&&canShowResult(job)&&result?<ExperiencePhoto kind="result" id={job.id} alt="AI试穿效果，仅供外观参考"/>:<ExperiencePhoto id={product.id} alt={product.title}/>}<span className="product-hero-tag">{job&&canShowResult(job)&&result?'AI试穿效果 · 非尺码保证':'试穿体验 · 暂无平台合作'}</span><button className="product-try-pill" disabled={working} onClick={()=>document.getElementById('tryon-controls')?.scrollIntoView({behavior:'smooth'})}>{view?.busy?'试穿中…':'AI试穿'}</button></section>
 <section className="product-summary panel"><strong>{product.title}</strong><div><span className="post-tag">{categoryNames[product.category]}</span><span className="muted">{product.source_label}</span></div><p className="muted">体验素材，无平台合作或成交价格。</p></section>
 <section id="tryon-controls" className="panel tryon-controls"><h2>试穿到我身上</h2><p className="muted">选择本人或已获许可的清晰正面照片。AI效果仅作外观参考。</p>
 <label className="tryon-picker"><AppIcon name="camera"/><span>{photo?'更换人物照片':'选择人物照片'}</span><input aria-label="试穿人物照片" type="file" accept="image/jpeg,image/png,image/webp" disabled={working} onChange={e=>{const f=e.target.files?.[0];if(!f)return;if(!['image/jpeg','image/png','image/webp'].includes(f.type)||f.size===0||f.size>10*1024*1024){setError('请选择10MB以内的JPG/PNG/WebP照片。');return;}setPhoto(f);setConsent(false);ticket.current=null;setRenew(false);setError('');}}/></label>
 {preview&&<img className="person-preview" src={preview} alt="已选人物照片，仅当前设备可见"/>}
 <label className="tryon-consent"><input type="checkbox" checked={consent} disabled={working} onChange={e=>setConsent(e.target.checked)}/><span>我有权使用所选照片，同意将人物与服饰图发送至FASHN生成试穿。输入临时处理，试穿结果在服务端可获取60分钟；请求记录不自动删除。本机照片与结果保留至删除任务或清空数据，不自动公开至社区。</span></label>
 {job&&<div className="tryon-status" role="status"><strong>{view?.label}</strong><span>{view?.progress}</span><p>{job.message}</p><small>试穿效果不构成尺码或合身保证。</small></div>}
 {error&&<p role="alert" className="error-text">{error}<br/>已选照片与输入保留。</p>}
 {!job&&!renew&&<button className="gradient-button" disabled={working||!photo||!consent} onClick={()=>void submit()}> {busy?'正在提交…':'开始AI试穿'}</button>}
 {(renew||job&&!view?.busy)&&<button className="soft-button" disabled={working||!photo||!consent} onClick={()=>setConfirmNew(true)}>重新确认试穿（新任务可能计费）</button>}
 {job&&<div className="button-row"><button className="soft-button" disabled={busy} onClick={()=>void refresh()}>{job.id===initialTaskId?'读取本地记录':'查询任务'}</button>{canShowResult(job)&&<button className="soft-button" onClick={()=>setResult(x=>!x)}>{result?'查看服饰原图':'查看试穿效果'}</button>}<button className="text-link" disabled={working} onClick={()=>setConfirmDelete(true)}>删除试穿记录</button></div>}
 </section></>}
 {confirmNew&&<div className="community-overlay"><section className="panel" role="alertdialog" aria-label="确认新试穿"><h2>创建新的试穿任务？</h2><p>这会重新提交图片并可能产生新费用。旧任务可能已被服务接收，请先查询核对。</p><button className="gradient-button" disabled={busy} onClick={()=>void submit(true)}>确认新任务</button><button className="soft-button" disabled={busy} onClick={()=>setConfirmNew(false)}>取消</button></section></div>}
 {confirmDelete&&<div className="community-overlay"><section className="panel" role="alertdialog" aria-label="删除试穿确认"><h2>删除本机试穿记录及照片？</h2><p>不代表取消远端任务或删除供应商请求元数据。</p>{error&&<p className="error-text">{error}</p>}<button className="gradient-button" disabled={busy} onClick={()=>void remove()}>确认删除</button><button className="soft-button" disabled={busy} onClick={()=>setConfirmDelete(false)}>取消</button></section></div>}
 </main>;
}
