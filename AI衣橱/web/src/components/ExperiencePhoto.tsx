import {useEffect,useRef,useState} from 'react';
import {watchTryonPhoto} from '../lib/tryonApi';
import type {PhotoState} from '../lib/tryonApi';
export default function ExperiencePhoto({kind='product',id,alt}:{kind?:'product'|'result';id:string;alt:string}){
 const [state,setState]=useState<PhotoState>({status:'loading',url:''});const resource=useRef<ReturnType<typeof watchTryonPhoto>|null>(null);
 useEffect(()=>{const r=watchTryonPhoto(kind,id,setState);resource.current=r;return()=>{r.dispose();resource.current=null;};},[kind,id]);
 return state.status==='ready'?<img src={state.url} alt={alt} onError={()=>resource.current?.fail()}/>:<span role="status" className={'experience-placeholder '+(state.status==='loading'?'skeleton':'')}>{state.status==='loading'?'照片加载中…':'照片暂不可用'}</span>;
}
