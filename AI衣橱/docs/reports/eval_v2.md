# 评测跑批 v2

运行时间戳：2026-11-13T15:52:47+08:00（Asia/Shanghai）
DASHSCOPE_MODEL：qwen3.8-flash
prompt_version：outfit_compose.v1；识别 item_extract.v2
分母：24；用例集 v2 共29条。

## 跳过：素材未备

- A01：跳过：素材未备（image_status=pending），不计入分母。
- A02：跳过：素材未备（image_status=pending），不计入分母。
- A03：跳过：素材未备（image_status=pending），不计入分母。
- A04：跳过：素材未备（image_status=pending），不计入分母。
- A05：跳过：素材未备（image_status=pending），不计入分母。

## 明细

R01–R09：本轮九张照片用item_extract.v2真实重新录制，评测读取本轮新原文，不复用v1。B01–B10：完整过滤→编排→真实客户端。
C01/C02：纯规则边界；C03–C05：客户端层注入，不计入真实模型失败。
C04 直接注入超时异常，未实际等待20s；注入耗时不能作为模型性能数据。
C04 UI黄条引用 [T7 截图](ui-t7/03-degraded.png)，未重做浏览器验收。
B05/B10 只保留一次基础真实生成，不以普通重复生成冒充 T9。
B类若实际降级，即使基础搭配可用，仍记硬性失败并保留模型侧归因。

| case_id | 通过 | 失败原因 | 归因 | 耗时 |
|---|---|---|---|---|
| [R01](raw/recognition_v2/R01.json) | 是 | — | — | 5304ms（n=1） |
| [R02](raw/recognition_v2/R02.json) | 否 | category：实际 top；期望 outer；sub_in：实际 拉链短款长袖T恤；期望 ['防晒服', '夹克', '风衣'] | IN | 6597ms（n=1） |
| [R03](raw/recognition_v2/R03.json) | 是 | — | — | 5869ms（n=1） |
| [R04](raw/recognition_v2/R04.json) | 是 | — | — | 8897ms（n=1） |
| [R05](raw/recognition_v2/R05.json) | 是 | — | — | 8441ms（n=1） |
| [R06](raw/recognition_v2/R06.json) | 是 | — | — | 9307ms（n=1） |
| [R07](raw/recognition_v2/R07.json) | 是 | — | — | 7581ms（n=1） |
| [R08](raw/recognition_v2/R08.json) | 是 | — | — | 8536ms（n=1） |
| [R09](raw/recognition_v2/R09.json) | 是 | — | — | 5194ms（n=1） |
| [B01](raw/compose_v2/B01.json) | 是 | — | — | 6046ms（n=1） |
| [B02](raw/compose_v2/B02.json) | 是 | — | — | 10855ms（n=1） |
| [B03](raw/compose_v2/B03.json) | 否 | outer_in：实际外套 ['W02', 'W03', 'W10']；只允许 ['W02', 'W10'] | BENCH | 5061ms（n=1） |
| [B04](raw/compose_v2/B04.json) | 是 | — | — | 5374ms（n=1） |
| [B05](raw/compose_v2/B05.json) | 否 | 依赖未实现（T9）；基础真实生成不等于排除交互/换一套验收 | 依赖未实现（T9） | 7077ms（n=1） |
| [B06](raw/compose_v2/B06.json) | 是 | — | — | 6037ms（n=1） |
| [B07](raw/compose_v2/B07.json) | 是 | — | — | 6174ms（n=1） |
| [B08](raw/compose_v2/B08.json) | 是 | — | — | 8807ms（n=1） |
| [B09](raw/compose_v2/B09.json) | 是 | — | — | 7605ms（n=1） |
| [B10](raw/compose_v2/B10.json) | 否 | distinct_sets_across_runs_gte；依赖未实现（T9）；基础真实生成不等于排除交互/换一套验收 | 依赖未实现（T9） | 7906ms（n=1） |
| [C01](raw/edges_v2/C01.json) | 是 | — | — | 0ms（n=1） |
| [C02](raw/edges_v2/C02.json) | 是 | — | — | 0ms（n=1） |
| [C03](raw/injections_v2/C03.json) | 是 | — | — | 8ms（n=1） |
| [C04](raw/injections_v2/C04.json) | 是 | — | — | 5ms（n=1） |
| [C05](raw/injections_v2/C05.json) | 是 | — | — | 5ms（n=1） |

## v1 vs v2

| 指标 | v1 | v2 |
|---|---|---|
| R03 | 失败 | 通过 |
| sub_in命中 | 8/9 | 8/9 |
| 硬性通过数 | 20/24 | 20/24 |

R03是否转绿：是；总通过数变化：+0。
绿转红：R02（category：实际 top；期望 outer;sub_in：实际 拉链短款长袖T恤；期望 ['防晒服', '夹克', '风衣']，IN）。
识别绿转红：R02。
B03归因按本轮更正为BENCH，expect与v1不变；v1报告及原文冻结，仍为20/24。
v2识别走client.vision、20s超时、temperature=0；v1录制脚本为120s且未显式设温度，变化不能全部归于prompt。
编排prompt未改；B类重复采样产生的变动另列，不能当作识别prompt效果。
Prompt只追加：sub 必须给具体款型名，禁止使用「长裤 / 裤子 / 上衣 / 外套 / 鞋子」等上位词；其余一字不改。

## 汇总

硬性通过数：20 / 24。
归因计数：IN=1；FILTER=0；COMPOSE=0；PARSE=0；BENCH=1；依赖未实现（T9）=2。
识别本轮录制耗时（min–max）：5194–9307ms, n=9
组合真实链路耗时（min–max）：5061–10855ms, n=10
规则边界耗时（min–max）：0–0ms, n=2
客户端注入耗时（min–max）：5–8ms, n=3
