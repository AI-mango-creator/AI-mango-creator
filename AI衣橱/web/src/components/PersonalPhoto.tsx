import {useEffect,useRef,useState} from 'react';
import {watchPersonalPhoto} from '../lib/personalApi';
import type {PhotoState} from '../lib/personalApi';
import AppIcon from './AppIcon';
export default function PersonalPhoto({path,alt}:{path:string;alt:string}){const [state,setState]=useState<PhotoState>({status:'loading',url:''});const ref=useRef<ReturnType<typeof watchPersonalPhoto>|null>(null);useEffect(()=>{const r=watchPersonalPhoto(path,setState);ref.current=r;return()=>r.dispose();},[path]);return state.status==='ready'?<img src={state.url} alt={alt} onError={()=>ref.current?.fail()}/>:<span className={'personal-photo-placeholder '+(state.status==='loading'?'skeleton':'')} role="status"><AppIcon name="person"/>{state.status==='loading'?'照片加载中…':'照片暂不可用'}</span>;}
