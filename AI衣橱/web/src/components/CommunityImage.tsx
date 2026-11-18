import { useEffect, useRef, useState } from 'react';
import { watchCommunityPhoto } from '../lib/communityApi';
import type { PhotoState } from '../lib/communityApi';
export default function CommunityImage({postId,mediaId,alt='穿搭照片'}:{postId:string;mediaId:string;alt?:string}){
 const [state,setState]=useState<PhotoState>({status:'loading',url:''});const resource=useRef<ReturnType<typeof watchCommunityPhoto>|null>(null);
 useEffect(()=>{const current=watchCommunityPhoto(postId,mediaId,setState);resource.current=current;return()=>{current.dispose();resource.current=null;};},[postId,mediaId]);
 return state.status==='ready'?<img className="community-photo" alt={alt} src={state.url} onError={()=>resource.current?.fail()}/>:<span className={`community-photo photo-placeholder ${state.status==='loading'?'skeleton':''}`} data-photo-state={state.status}>{state.status==='loading'?'照片加载中…':'照片暂不可用'}</span>;
}
