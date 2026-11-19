import type {TryonStatus} from './tryonApi';
export function getTryonView(status:TryonStatus){const busy=['submitting','starting','in_queue','processing'].includes(status);return{busy,progress:status==='completed'?'1 / 1':'0 / 1',label:status==='completed'?'试穿完成':busy?'试穿中…':status==='unknown'?'提交结果待核':status==='timed_out'?'等待已结束':'试穿未成功'};}
export function canShowResult(job:{status:TryonStatus;has_result:boolean}){return job.status==='completed'&&job.has_result;}
