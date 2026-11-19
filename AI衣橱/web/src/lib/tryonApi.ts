import {deviceHeaders,getDeviceId} from './deviceId';
export type TryonCategory='tops'|'bottoms'|'one-pieces';
export type Product={id:string;title:string;category:TryonCategory;source_label:string};
export type TryonStatus='submitting'|'starting'|'in_queue'|'processing'|'completed'|'failed'|'unknown'|'timed_out';
export type Tryon={id:string;product_id:string;status:TryonStatus;message:string;has_result:boolean;latency_ms:number;version:string};
export type Ticket={ticket:string;request_id:string;expires_at:number};
export type PhotoState={status:'loading'|'ready'|'error';url:string};
export class TryonApiError extends Error{constructor(message:string,public status:number){super(message);}}
const obj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==='object';
export const categoryNames:Record<TryonCategory,string>={tops:'上装',bottoms:'下装','one-pieces':'裙装'};
async function request(path:string,init:RequestInit={},signal?:AbortSignal,fetcher:typeof fetch=fetch,blob=false,expectedOwner=getDeviceId()):Promise<unknown>{
 if(getDeviceId()!==expectedOwner)throw new Error('设备已变化，请重新打开试穿。');
 let r:Response;try{r=await fetcher('/api'+path,{...init,headers:deviceHeaders(init.headers),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(25000)]):AbortSignal.timeout(25000)});}catch(e){if(signal?.aborted)throw e;throw new Error('连接中断，当前照片仍保留。提交可能已被接收，请先查询任务，不要重复生成。');}
 let value:unknown;try{value=r.status===204?null:r.ok&&blob?await r.blob():await r.json();}catch{throw new Error('试穿响应格式有误，请重新查询任务。');}
 if(getDeviceId()!==expectedOwner)throw new Error('设备已变化，请重新打开试穿。');
 if(!r.ok){const message=obj(value)&&typeof value.detail==='string'&&/[\u4e00-\u9fff]/.test(value.detail)?value.detail:'试穿暂不可用，请稍后重试。';throw new TryonApiError(message,r.status);}return value;
}
function product(x:unknown):Product{if(!obj(x)||typeof x.id!=='string'||typeof x.title!=='string'||typeof x.source_label!=='string'||!Object.hasOwn(categoryNames,String(x.category)))throw new Error('体验服饰信息无效，请重载。');return x as Product;}
function job(x:unknown):Tryon{if(!obj(x)||typeof x.id!=='string'||typeof x.product_id!=='string'||!['submitting','starting','in_queue','processing','completed','failed','unknown','timed_out'].includes(String(x.status))||typeof x.message!=='string'||typeof x.has_result!=='boolean'||typeof x.latency_ms!=='number'||!Number.isFinite(x.latency_ms)||typeof x.version!=='string'||(x.status==='completed'&&!x.has_result))throw new Error('试穿任务信息无效，请重新查询。');return x as Tryon;}
export async function products(signal?:AbortSignal,fetcher:typeof fetch=fetch){const data=await request('/experience/products',{},signal,fetcher);if(!Array.isArray(data))throw new Error('服饰目录格式无效。');return data.map(product);}
export async function getProduct(id:string,signal?:AbortSignal){return product(await request('/experience/products/'+encodeURIComponent(id),{},signal));}
export async function issueTicket(id:string,signal?:AbortSignal,fetcher:typeof fetch=fetch){const data=await request('/tryons/ticket?product_id='+encodeURIComponent(id),{},signal,fetcher);if(!obj(data)||typeof data.ticket!=='string'||typeof data.request_id!=='string'||typeof data.expires_at!=='number')throw new Error('试穿凭据无效。');return data as Ticket;}
export async function recentTryons(id:string,signal?:AbortSignal){const data=await request('/tryons?product_id='+encodeURIComponent(id),{},signal);if(!Array.isArray(data))throw new Error('试穿记录无效。');return data.map(job);}
export async function getTryon(id:string,signal?:AbortSignal,fetcher:typeof fetch=fetch){return job(await request('/tryons/'+encodeURIComponent(id),{},signal,fetcher));}
export async function deleteTryon(id:string){await request('/tryons/'+encodeURIComponent(id),{method:'DELETE'});}
export async function createTryon(id:string,ticket:string,photo:File,consent:boolean,signal?:AbortSignal,fetcher:typeof fetch=fetch,expectedOwner=getDeviceId()){
 if(!consent)throw new Error('请先同意照片使用权和向试穿服务发送处理。');if(!['image/jpeg','image/png','image/webp'].includes(photo.type)||!photo.size||photo.size>10*1024*1024)throw new Error('请选择10MB以内的JPG/PNG/WebP照片。');
 const data=new FormData();data.set('product_id',id);data.set('ticket',ticket);data.set('photo',photo);data.set('consent','true');return job(await request('/tryons',{method:'POST',body:data},signal,fetcher,false,expectedOwner));
}
export function watchTryonPhoto(kind:'product'|'result',id:string,onState:(x:PhotoState)=>void,fetcher:typeof fetch=fetch){const c=new AbortController();let url='';function release(){if(url){URL.revokeObjectURL(url);url='';}}function fail(){release();if(!c.signal.aborted)onState({status:'error',url:''});}onState({status:'loading',url:''});
 void request(kind==='product'?'/experience/products/'+encodeURIComponent(id)+'/photo':'/tryons/'+encodeURIComponent(id)+'/result',{},c.signal,fetcher,true).then(data=>{if(c.signal.aborted)return;if(!(data instanceof Blob)||!data.type.startsWith('image/'))throw new Error();url=URL.createObjectURL(data);onState({status:'ready',url});}).catch(fail);return{fail,dispose(){c.abort();release();}};
}

// One explicit attempt owns one ticket, including lost-response and concurrent retries.
export class TryonAttempt{
 private pending:Promise<Ticket>|null=null;
 constructor(private productId:string,private owner=getDeviceId()){}
 async submit(photo:File,consent:boolean,signal?:AbortSignal,fetcher:typeof fetch=fetch){
  if(getDeviceId()!==this.owner)throw new Error('设备已变化，请重新打开试穿。');
  if(!consent)throw new Error('请先确认照片处理说明。');
  if(!this.pending)this.pending=issueTicket(this.productId,signal,fetcher).catch(e=>{this.pending=null;throw e;});
  const token=await this.pending;
  return createTryon(this.productId,token.ticket,photo,consent,signal,fetcher,this.owner);
 }
}
