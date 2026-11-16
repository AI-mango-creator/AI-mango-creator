# 评测跑批 v1

运行时间戳：2026-11-13T15:27:39+08:00（Asia/Shanghai）
DASHSCOPE_MODEL：qwen3.8-flash
prompt_version：outfit_compose.v1；识别 item_extract.v1
分母：24；用例集 v2 共29条。

## 跳过：素材未备

- A01：跳过：素材未备（image_status=pending），不计入分母。
- A02：跳过：素材未备（image_status=pending），不计入分母。
- A03：跳过：素材未备（image_status=pending），不计入分母。
- A04：跳过：素材未备（image_status=pending），不计入分母。
- A05：跳过：素材未备（image_status=pending），不计入分母。

## 明细

R01–R09：重放自 2026-11-13 录制，未重新调用视觉模型。B01–B10：完整过滤→编排→真实客户端。
C01/C02：纯规则边界；C03–C05：客户端层注入，不计入真实模型失败。
C04 直接注入超时异常，未实际等待20s；注入耗时不能作为模型性能数据。
C04 UI黄条引用 [T7 截图](ui-t7/03-degraded.png)，未重做浏览器验收。
B05/B10 只保留一次基础真实生成，不以普通重复生成冒充 T9。
B类若实际降级，即使基础搭配可用，仍记硬性失败并保留模型侧归因。

| case_id | 通过 | 失败原因 | 归因 | 耗时 |
|---|---|---|---|---|
| [R01](raw/recognition/R01.json) | 是 | — | — | 23215ms（n=1） |
| [R02](raw/recognition/R02.json) | 是 | — | — | 8386ms（n=1） |
| [R03](raw/recognition/R03.json) | 否 | sub_in：实际 长裤；期望 ['阔腿裤', '运动裤', '休闲裤'] | IN | 16893ms（n=1） |
| [R04](raw/recognition/R04.json) | 是 | — | — | 24888ms（n=1） |
| [R05](raw/recognition/R05.json) | 是 | — | — | 17816ms（n=1） |
| [R06](raw/recognition/R06.json) | 是 | — | — | 18302ms（n=1） |
| [R07](raw/recognition/R07.json) | 是 | — | — | 23487ms（n=1） |
| [R08](raw/recognition/R08.json) | 是 | — | — | 7454ms（n=1） |
| [R09](raw/recognition/R09.json) | 是 | — | — | 5880ms（n=1） |
| [B01](raw/compose/B01.json) | 是 | — | — | 5743ms（n=1） |
| [B02](raw/compose/B02.json) | 是 | — | — | 6738ms（n=1） |
| [B03](raw/compose/B03.json) | 否 | outer_in：实际外套 ['W02', 'W03', 'W10']；只允许 ['W02', 'W10'] | COMPOSE | 6266ms（n=1） |
| [B04](raw/compose/B04.json) | 是 | — | — | 6542ms（n=1） |
| [B05](raw/compose/B05.json) | 否 | 依赖未实现（T9）；基础真实生成不等于排除交互/换一套验收 | 依赖未实现（T9） | 7056ms（n=1） |
| [B06](raw/compose/B06.json) | 是 | — | — | 11923ms（n=1） |
| [B07](raw/compose/B07.json) | 是 | — | — | 5774ms（n=1） |
| [B08](raw/compose/B08.json) | 是 | — | — | 5664ms（n=1） |
| [B09](raw/compose/B09.json) | 是 | — | — | 5969ms（n=1） |
| [B10](raw/compose/B10.json) | 否 | distinct_sets_across_runs_gte；依赖未实现（T9）；基础真实生成不等于排除交互/换一套验收 | 依赖未实现（T9） | 5905ms（n=1） |
| [C01](raw/edges/C01.json) | 是 | — | — | 0ms（n=1） |
| [C02](raw/edges/C02.json) | 是 | — | — | 0ms（n=1） |
| [C03](raw/injections/C03.json) | 是 | — | — | 8ms（n=1） |
| [C04](raw/injections/C04.json) | 是 | — | — | 4ms（n=1） |
| [C05](raw/injections/C05.json) | 是 | — | — | 5ms（n=1） |

## 汇总

硬性通过数：20 / 24。
归因计数：IN=1；FILTER=0；COMPOSE=1；PARSE=0；依赖未实现（T9）=2。
识别原录制耗时（min–max）：5880–24888ms, n=9
组合真实链路耗时（min–max）：5664–11923ms, n=10
规则边界耗时（min–max）：0–0ms, n=2
客户端注入耗时（min–max）：4–8ms, n=3
