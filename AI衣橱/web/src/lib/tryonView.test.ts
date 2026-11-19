import {expect,it} from 'vitest';
import {getTryonView,canShowResult} from './tryonView';
it('处理中不伪造百分比，终态不再自动轮询',()=>{expect(getTryonView('processing')).toMatchObject({busy:true,progress:'0 / 1'});expect(getTryonView('unknown').busy).toBe(false);expect(getTryonView('timed_out').busy).toBe(false);});
it('只有completed且有真实结果时显示效果图',()=>{expect(canShowResult({status:'processing',has_result:true})).toBe(false);expect(canShowResult({status:'completed',has_result:true})).toBe(true);expect(canShowResult({status:'completed',has_result:false})).toBe(false);});
