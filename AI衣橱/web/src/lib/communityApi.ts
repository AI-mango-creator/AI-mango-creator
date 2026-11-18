import { deviceHeaders, getDeviceId } from './deviceId';
export type CommunityTab = 'following'|'all'|'outfits'|'votes';
export type PostKind = 'photo'|'outfit'|'poll'|'buy';
export type PublicAuthor = { id:string; nickname:string };
export type PublicMedia = { id:string; caption:string };
export type PublicPost = { id:string; author:PublicAuthor; kind:PostKind; title:string; body:string; created_at:string; media:PublicMedia[]; options:{id:string;label:string;media_id:string|null;votes:number}[]; likes:number;comments:number;votes:number;liked:boolean;following:boolean;my_vote:string|null;can_delete:boolean };
export type PublicComment = { id:string;author:PublicAuthor;text:string;created_at:string;can_delete:boolean };
export type PostDraft = { draft_id:string;kind:PostKind;title:string;body:string;item_ids:string[];options:{label:string}[];photos:File[] };
export type PhotoState = {status:'loading'|'ready'|'error';url:string};
export const postKindLabels:Record<PostKind,string> = {photo:'穿搭分享',outfit:'搭配分享',poll:'穿搭投票',buy:'买不买'};
const base='/api/community';
async function request(path:string, init:RequestInit={}, signal?:AbortSignal, fetcher:typeof fetch=fetch, blob=false):Promise<unknown>{
  const owner=getDeviceId();const timeout=AbortSignal.timeout(init.method==='POST'?45000:12000);
  let response:Response;
  try{response=await fetcher(base+path,{...init,headers:deviceHeaders(init.headers),signal:signal?AbortSignal.any([signal,timeout]):timeout});}
  catch(error){if(signal?.aborted)throw error;throw new Error('连接失败，请检查网络后重试，当前输入仍保留。');}
  if(getDeviceId()!==owner)throw new Error('设备标识已变化，请重新打开社区。');
  if(response.status===204)return null;
  let data:unknown;try{data=response.ok&&blob?await response.blob():await response.json();}catch{throw new Error('社区响应格式有误，请重试。');}
  if(!response.ok){const detail=record(data)&&typeof data.detail==='string'?data.detail:'';throw new Error(/[\u4e00-\u9fff]/.test(detail)?detail:'请求失败，请稍后重试。');}return data;
}
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object';
const author=(x:unknown)=>record(x)&&typeof x.id==='string'&&typeof x.nickname==='string';
const count=(x:unknown)=>typeof x==='number'&&Number.isInteger(x)&&x>=0;
function post(data:unknown):PublicPost{
 if(!record(data)||typeof data.id!=='string'||!author(data.author)||!Object.hasOwn(postKindLabels,String(data.kind))||typeof data.title!=='string'||typeof data.body!=='string'||typeof data.created_at!=='string'||!Number.isFinite(Date.parse(data.created_at))||!Array.isArray(data.media)||data.media.some(m=>!record(m)||typeof m.id!=='string'||typeof m.caption!=='string')||!Array.isArray(data.options)||data.options.some(o=>!record(o)||typeof o.id!=='string'||typeof o.label!=='string'||!(o.media_id===null||typeof o.media_id==='string')||!count(o.votes))||!count(data.likes)||!count(data.comments)||!count(data.votes)||typeof data.liked!=='boolean'||typeof data.following!=='boolean'||typeof data.can_delete!=='boolean'||!(data.my_vote===null||typeof data.my_vote==='string'))throw new Error('帖子字段有误，请刷新重试。');return data as PublicPost;
}
function comment(data:unknown):PublicComment{if(!record(data)||typeof data.id!=='string'||!author(data.author)||typeof data.text!=='string'||typeof data.created_at!=='string'||typeof data.can_delete!=='boolean')throw new Error('评论字段有误，请重试。');return data as PublicComment;}
const id=(x:string)=>encodeURIComponent(x);
export async function communityFeed(tab:CommunityTab,cursor:string|null=null,signal?:AbortSignal,fetcher:typeof fetch=fetch){const q=new URLSearchParams({tab,limit:'20'});if(cursor)q.set('cursor',cursor);const data=await request('/posts?'+q,{},signal,fetcher);if(!record(data)||!Array.isArray(data.posts)||!(data.next_cursor===null||typeof data.next_cursor==='string'))throw new Error('社区列表字段有误，请重试。');return {posts:data.posts.map(post),next_cursor:data.next_cursor as string|null};}
export async function communityPost(postId:string,signal?:AbortSignal,fetcher:typeof fetch=fetch){return post(await request('/posts/'+id(postId),{},signal,fetcher));}
export function newPostDraft(kind:PostKind):PostDraft{return {draft_id:crypto.randomUUID(),kind,title:kind==='buy'?'这套值得入手吗？':kind==='poll'?'哪套更适合我？':'',body:'',item_ids:[],options:kind==='poll'?[{label:'搭配一'},{label:'搭配二'}]:[],photos:[]};}
export function validatePostDraft(d:PostDraft){
 if(!d.title.trim()||d.title.trim().length>80||d.body.trim().length>2000)throw new Error('请填写1至80字标题，正文不超过2000字。');
 if(d.kind==='outfit'){if(d.item_ids.length<2||d.item_ids.length>8||new Set(d.item_ids).size!==d.item_ids.length||d.photos.length)throw new Error('请选择2至8件不同的自有衣物。');}
 else if(d.item_ids.length)throw new Error('此类帖子不能附带衣柜单品。');
 if(d.kind==='photo'&&(d.photos.length<1||d.photos.length>9)||d.kind==='buy'&&d.photos.length!==1||d.kind==='poll'&&(d.options.length<2||d.options.length>4||d.photos.length!==d.options.length||d.options.some(o=>!o.label.trim()||o.label.trim().length>80)))throw new Error('请检查图片数量与投票选项。');
 if(d.photos.some(f=>!['image/jpeg','image/png','image/webp'].includes(f.type)||f.size===0||f.size>10*1024*1024)||d.photos.reduce((sum,f)=>sum+f.size,0)>30*1024*1024)throw new Error('支持JPG/PNG/WebP，单图≤10MB、每帖≤30MB。');
}
export async function publishPost(draft:PostDraft,fetcher:typeof fetch=fetch,signal?:AbortSignal,expectedOwner=getDeviceId()){if(getDeviceId()!==expectedOwner)throw new Error('设备标识已变化，请重新打开发布页。');validatePostDraft(draft);const {photos,...metadata}=draft;const form=new FormData();form.set('metadata',JSON.stringify({...metadata,title:metadata.title.trim(),body:metadata.body.trim(),options:metadata.options.map(x=>({label:x.label.trim()}))}));photos.forEach(f=>form.append('photos',f));return post(await request('/posts',{method:'POST',body:form},signal,fetcher));}
export async function deletePost(postId:string){await request('/posts/'+id(postId),{method:'DELETE'});}
export async function followAuthor(authorId:string,enabled:boolean){const data=await request('/authors/'+id(authorId)+'/follow',{method:enabled?'PUT':'DELETE'});if(!record(data)||typeof data.following!=='boolean')throw new Error('关注状态有误，请刷新。');return data.following;}
export async function likePost(postId:string,enabled:boolean){return post(await request('/posts/'+id(postId)+'/like',{method:enabled?'PUT':'DELETE'}));}
export async function votePost(postId:string,optionId:string,fetcher:typeof fetch=fetch){return post(await request('/posts/'+id(postId)+'/vote',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({option_id:optionId})},undefined,fetcher));}
export async function communityComments(postId:string,cursor:string|null=null,signal?:AbortSignal){const q=new URLSearchParams({limit:'20'});if(cursor)q.set('cursor',cursor);const data=await request('/posts/'+id(postId)+'/comments?'+q,{},signal);if(!record(data)||!Array.isArray(data.comments)||!(data.next_cursor===null||typeof data.next_cursor==='string'))throw new Error('评论列表有误，请重试。');return {comments:data.comments.map(comment),next_cursor:data.next_cursor as string|null};}
export async function addComment(postId:string,clientId:string,text:string,fetcher:typeof fetch=fetch){if(!text.trim()||text.trim().length>500)throw new Error('评论需1至500字。');return comment(await request('/posts/'+id(postId)+'/comments',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({client_id:clientId,text:text.trim()})},undefined,fetcher));}
export async function deleteComment(commentId:string){await request('/comments/'+id(commentId),{method:'DELETE'});}
export function watchCommunityPhoto(postId:string,mediaId:string,onState:(s:PhotoState)=>void,fetcher:typeof fetch=fetch){
 const control=new AbortController();let url='';function release(){if(url){URL.revokeObjectURL(url);url='';}}
 function fail(){release();if(!control.signal.aborted)onState({status:'error',url:''});}onState({status:'loading',url:''});
 void request('/posts/'+id(postId)+'/photos/'+id(mediaId),{},control.signal,fetcher,true).then(data=>{if(control.signal.aborted)return;if(!(data instanceof Blob)||!data.type.startsWith('image/'))throw new Error('照片无效');url=URL.createObjectURL(data);onState({status:'ready',url});}).catch(fail);
 return {fail,dispose(){control.abort();release();}};
}
