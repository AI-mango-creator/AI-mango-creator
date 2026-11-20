import {deviceHeaders,getDeviceId} from './deviceId';
import type {PublicPost} from './communityApi';
import type {WardrobeItem} from './api';
export type Overview={nickname:string;has_avatar:boolean;avatar_version:string;balance:number;following:number;followers:number;interactions:number};
export type Ootd={id:string;worn_on:string;title:string;note:string;kind:'photo'|'outfit';set_id:string|null;created_at:string;updated_at:string;has_photo:boolean;source_deleted:boolean};
export type OutfitRecord={type:'outfit';id:string;title:string;reason:string;degraded:boolean;temp_c:number;occasion:string;created_at:null;items:WardrobeItem[];slots:Record<string,string>};
export type PostRecord={type:'post';id:string;title:string;created_at:string;post:PublicPost};
export type HistoryRecord={type:'tryon';id:string;product_id:string;title:string;created_at:string;status:string;message:string;has_result:boolean};
export type ContentRecord=OutfitRecord|PostRecord|HistoryRecord;
export type Person={id:string;nickname:string;created_at:string};
export type Interaction={id:string;type:'like'|'comment'|'follow'|'vote';created_at:string;text:string;title:string;post_id:string|null;actor:{id:string;nickname:string}|null};
export type PointsPage={balance:number;items:{id:string;day:string;delta:number;reason:string;created_at:string}[];next_cursor:string|null};
export type PageData<T>={items:T[];next_cursor:string|null};
export type PhotoState={status:'loading'|'ready'|'error';url:string};
export type Purpose='ootd'|'feedback'|'settings'|'avatar'|'favorite';
const obj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==='object';
const num=(x:unknown)=>typeof x==='number'&&Number.isInteger(x)&&x>=0;
const str=(x:unknown):x is string=>typeof x==='string';
function bad():never{throw new Error('个人数据格式有误，请重新加载。');}
export async function personalRequest(path:string,init:RequestInit={},signal?:AbortSignal,fetcher:typeof fetch=fetch,blob=false,expected=getDeviceId()):Promise<unknown>{
 if(getDeviceId()!==expected)throw new Error('设备身份已变化，请重新打开页面。');
 let r:Response;try{r=await fetcher('/api/me'+path,{...init,headers:deviceHeaders(init.headers),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(20000)]):AbortSignal.timeout(20000)});}catch(e){if(signal?.aborted)throw e;throw new Error('连接失败，请检查网络后重试；当前输入仍保留。');}
 if(getDeviceId()!==expected)throw new Error('设备身份已变化，请重新打开页面。');
 let value:unknown;try{value=r.status===204?null:r.ok&&blob?await r.blob():await r.json();}catch{throw new Error('个人数据响应有误，请重试。');}
 if(getDeviceId()!==expected)throw new Error('设备身份已变化，请重新打开页面。');
 if(!r.ok)throw new Error(obj(value)&&str(value.detail)&&/[\u4e00-\u9fff]/.test(value.detail)?value.detail:'操作未完成，请稍后重试。');return value;
}
export async function getOverview(signal?:AbortSignal,f:typeof fetch=fetch):Promise<Overview>{const x=await personalRequest('',{},signal,f);if(!obj(x)||!str(x.nickname)||typeof x.has_avatar!=='boolean'||!str(x.avatar_version)||!['balance','following','followers','interactions'].every(k=>num(x[k])))bad();return x as Overview;}
export async function checkIn(f:typeof fetch=fetch){const x=await personalRequest('/points/check-in',{method:'POST'},undefined,f);if(!obj(x)||typeof x.awarded!=='boolean'||!str(x.day)||!num(x.balance))bad();return x as {awarded:boolean;day:string;balance:number};}
let lastVisit=0,lastDay='';
export async function visitCheckin(){const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date());if(Date.now()-lastVisit<60000&&lastDay===day)return;try{await checkIn();lastVisit=Date.now();lastDay=day;}catch{/* Failed visit never blocks the application; points page can retry. */}}
function isOotd(x:unknown):x is Ootd{return obj(x)&&str(x.id)&&str(x.worn_on)&&str(x.title)&&str(x.note)&&['photo','outfit'].includes(String(x.kind))&&(x.set_id===null||str(x.set_id))&&str(x.created_at)&&str(x.updated_at)&&typeof x.has_photo==='boolean'&&typeof x.source_deleted==='boolean';}
function isContent(x:unknown):x is ContentRecord{if(!obj(x)||!str(x.id)||!str(x.title))return false;if(x.type==='tryon')return str(x.product_id)&&str(x.created_at)&&['submitting','starting','in_queue','processing','completed','failed','unknown','timed_out'].includes(String(x.status))&&str(x.message)&&typeof x.has_result==='boolean';if(x.type==='post')return str(x.created_at)&&obj(x.post)&&x.post.id===x.id&&Array.isArray(x.post.media)&&obj(x.post.author)&&str(x.post.author.nickname);return x.type==='outfit'&&str(x.reason)&&typeof x.degraded==='boolean'&&Array.isArray(x.items)&&x.items.every(i=>obj(i)&&i.owner_id===getDeviceId())&&obj(x.slots);}
export async function getPersonalPage<T=ContentRecord>(path:string,signal?:AbortSignal,f:typeof fetch=fetch):Promise<PageData<T>>{const x=await personalRequest(path,{},signal,f);if(!obj(x)||!Array.isArray(x.items)||!(x.next_cursor===null||str(x.next_cursor)))bad();const valid=path.startsWith('/ootds')?isOotd:path.startsWith('/people')?(v:unknown)=>obj(v)&&str(v.id)&&str(v.nickname)&&str(v.created_at):path.startsWith('/interactions')?(v:unknown)=>obj(v)&&str(v.id)&&str(v.text)&&str(v.created_at)&&['like','comment','follow','vote'].includes(String(v.type))&&(v.actor===null||obj(v.actor)):(v:unknown)=>isContent(v);if(x.items.some(i=>!valid(i)))bad();return x as PageData<T>;}
export async function getPoints(cursor:string|null=null,signal?:AbortSignal):Promise<PointsPage>{const x=await personalRequest('/points'+(cursor?'?cursor='+encodeURIComponent(cursor):''),{},signal);if(!obj(x)||!num(x.balance)||!Array.isArray(x.items)||!(x.next_cursor===null||str(x.next_cursor))||x.items.some(i=>!obj(i)||!str(i.id)||!str(i.day)||i.delta!==10||!str(i.created_at)))bad();return x as PointsPage;}
export class PersonalAttempt{
 private pending:Promise<string>|null=null;
 private owner=getDeviceId();
 constructor(private purpose:Purpose){}
 private async ticket(f:typeof fetch,signal?:AbortSignal){if(!this.pending)this.pending=personalRequest('/write-tickets?purpose='+this.purpose,{method:'POST'},signal,f,false,this.owner).then(x=>{if(!obj(x)||!str(x.ticket)||!str(x.request_id)||typeof x.expires_at!=='number')bad();return x.ticket;}).catch(e=>{this.pending=null;throw e;});return this.pending;}
 async json(path:string,method:string,body:Record<string,unknown>,f:typeof fetch=fetch,signal?:AbortSignal){const ticket=await this.ticket(f,signal);return personalRequest(path,{method,headers:{'content-type':'application/json'},body:JSON.stringify({...body,ticket})},signal,f,false,this.owner);}
 async upload(path:string,metadata:Record<string,unknown>|null,photo:File|null,f:typeof fetch=fetch,signal?:AbortSignal){const ticket=await this.ticket(f,signal);const form=new FormData();if(metadata)form.set('metadata',JSON.stringify({...metadata,ticket}));else form.set('ticket',ticket);if(photo)form.set('photo',photo);return personalRequest(path,{method:metadata?'POST':'PUT',body:form},signal,f,false,this.owner);}
}
export async function favoriteStatus(id:string,signal?:AbortSignal){const x=await personalRequest('/favorites/'+encodeURIComponent(id),{},signal);if(!obj(x)||typeof x.saved!=='boolean')bad();return x.saved;}
export async function setFavorite(id:string,enabled:boolean,attempt=new PersonalAttempt('favorite')){const x=await attempt.json('/favorites/'+encodeURIComponent(id),enabled?'PUT':'DELETE',{});if(!obj(x)||typeof x.saved!=='boolean')bad();return x.saved;}
export async function getOotd(id:string,signal?:AbortSignal):Promise<Ootd>{const x=await personalRequest('/ootds/'+encodeURIComponent(id),{},signal);if(!isOotd(x))bad();return x;}
export async function getSavedOutfit(id:string,signal?:AbortSignal):Promise<OutfitRecord>{const x=await personalRequest('/outfits/'+encodeURIComponent(id),{},signal);if(!isContent(x)||x.type!=='outfit')bad();return x;}
export async function deleteOotd(id:string){await personalRequest('/ootds/'+encodeURIComponent(id),{method:'DELETE'});}
export async function updateOotd(id:string,values:{worn_on:string;title:string;note:string}){return personalRequest('/ootds/'+encodeURIComponent(id),{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify(values)});}
export function watchPersonalPhoto(path:string,onState:(x:PhotoState)=>void,f:typeof fetch=fetch){const c=new AbortController();const owner=getDeviceId();let url='';function release(){if(url){URL.revokeObjectURL(url);url='';}}function fail(){release();if(!c.signal.aborted)onState({status:'error',url:''});}function identity(){if(getDeviceId()!==owner){release();onState({status:'error',url:''});c.abort();}}globalThis.addEventListener?.('storage',identity);onState({status:'loading',url:''});void personalRequest(path,{},c.signal,f,true).then(x=>{if(c.signal.aborted)return;if(!(x instanceof Blob)||!x.type.startsWith('image/'))bad();url=URL.createObjectURL(x);onState({status:'ready',url});}).catch(fail);return{fail,dispose(){c.abort();release();globalThis.removeEventListener?.('storage',identity);}};}

export async function getHistoricalTryon(id:string,signal?:AbortSignal){const x=await personalRequest('/tryons/'+encodeURIComponent(id),{},signal);if(!obj(x)||!str(x.id)||!str(x.product_id)||!str(x.status)||!str(x.message)||typeof x.has_result!=='boolean'||typeof x.latency_ms!=='number'||!str(x.version))bad();return x as import('./tryonApi').Tryon;}
