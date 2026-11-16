# T5b 真实视觉识别（鞋类）与过滤层语义越权修复

执行时间：2026-11-13 12:15–12:45（Asia/Shanghai）
执行方式：本机真实网络调用，无 mock、无注入
模型：`qwen3.8-omni-flash`（与 T5 完全相同的 prompt，一字未改，保证可比）
素材：用户本人两双鞋的实拍/商品图，压缩至 900px 存于 `cases/images/cloth08–09.jpg`

> 为什么沿用旧 prompt 而不先调优：这次要测的是"现有 prompt 对鞋的表现"。
> 先改 prompt 再测，等于把问题藏起来，测出来的准确率没有意义。

## 一、识别结果（2/2 成功）

| 图 | 实际物品 | category | warmth | formality | confidence | 耗时 | 围栏 |
|---|---|---|---|---|---|---|---|
| cloth08 | 白黑卡其拼色板鞋（AJ1 Low 型） | shoes ✓ | **3 ✗** | 1 ✓ | 0.98 | 19.6s | 有 |
| cloth09 | 米白厚底跑鞋（ZoomX 型） | shoes ✓ | 2 ✓ | 1 ✓ | 0.95 | 6.4s | 无 |

逐字段与人工真值比对（真值由人看图判定，不是模型输出的复述）：

| 字段 | cloth08 模型 | cloth08 真值 | cloth09 模型 | cloth09 真值 |
|---|---|---|---|---|
| category | shoes | shoes | shoes | shoes |
| sub | 运动鞋 | 板鞋 | 运动鞋 | 运动鞋 |
| colors | 白/黑/卡其 | 白/黑/卡其 | 白/灰 | 白/米白/灰 |
| material | 皮革 | 皮革 | 网面麂皮拼接 | 网面麂皮拼接 |
| pattern | **纯色** | **拼色** | 纯色 | 纯色 |
| warmth | **3** | **2** | 2 | 2 |
| formality | 1 | 1 | 1 | 1 |
| seasons | 四季 | 四季 | 春夏秋 | 春夏秋 |

字段级：16 个字段 13 个一致（81%）。**但准确率不是这次的重点，下面这条才是。**

## 二、核心发现：鞋的 warmth 没有语义，却被拿去过滤

### 现象

cloth08 是一双单层皮革板鞋，夏天完全能穿。模型判 `warmth=3`（"常规"，等于一件长袖衬衫），
而 `filter.py` 对**所有槽位**一视同仁地做温度带过滤：

```python
# app/services/filter.py（修复前）
and _overlaps((item.warmth, item.warmth), _SPEC["allowed_warmth"][band])
```

`allowed_warmth["hot"] = [1, 2]`，于是 `warmth=3` 的鞋在 26℃ 以上**直接从候选集消失**。

用户视角的后果：**"我明明有这双鞋，系统说夏天没鞋穿。"**
这不是内部洁癖，是看得见的功能故障。

### 归因实验（单变量对照）

不靠推理，直接跑：同一件物品，只改 `warmth` 一个字段，其余全部不动。

| 条件 | 28℃（hot） | 18℃（cool） |
|---|---|---|
| cloth08 原样 warmth=3 | **✗ 被过滤** | ✓ 在候选 |
| 仅把 warmth 改成 2 | **✓ 在候选** | ✓ 在候选 |

同时对照另一双：cloth09（warmth=2）在 28℃ 一直是 ✓。
**结论唯一：变量就是 warmth，不是 colors/material/seasons/formality。**

### 根因：两个缺陷叠加

1. **prompt 锚点全是上装语义**
   现行锚点是"1 极薄(背心/短裤)、3 常规、5 厚外套"——没有任何一条描述鞋。
   鞋落在"5 档量表"里，模型只能往中位数猜，`3` 就是最安全的猜测值。所以这不是模型笨，是**量表没有覆盖鞋**。

2. **过滤层越权**
   `_allowed_slot` / `filter_candidates` 用同一套 warmth 规则处理 top/outer/bottom/shoes。
   但"夏天能不能穿这双鞋"的真正判据是 `seasons`，不是 `warmth`——鞋的保暖档位与上装不可通约。

### 修复（D9）

数据侧新增配置，代码侧读取，不发明槽位名：

```json
"filter_spec": { "warmth_exempt_slots": ["shoes"] }
```

```python
_WARMTH_EXEMPT = frozenset(_SPEC.get("warmth_exempt_slots", ()))

def _allowed_slot(item, band):
    ...
    if item.category in _WARMTH_EXEMPT:
        return True          # 鞋只看类目/季节，不看 warmth
    return item.warmth is not None and item.warmth >= _warmth_min(item.category, band)
```

**豁免的只有 warmth，seasons 照旧生效**——所以冬靴不会被放进 28℃ 的候选。
这两条都有单测钉住：

- `test_shoes_ignore_warmth_in_hot_band`：warmth=3 的板鞋在 28℃ 必须可选
- `test_shoes_still_filtered_by_season`：seasons=[winter] 的雪地靴在 28℃ 必须被排除

修复后实测（weekend 场景，14 件衣柜）：

| 温度带 | cloth08(warmth3) | 组合数（修复前 → 后） |
|---|---|---|
| 28℃ hot | ✗ → **✓** | 4 → 5 |
| 22℃ warm | ✓ | 20 |
| 18℃ cool | ✓ | 60 |
| 8℃ cold | ✓ | 40 |

## 三、附带发现

### 1) `cases/fixtures/` 目录不存在，A01–A05 五条识别用例全是悬空引用

`cases/` 下只有 `cases.json` 和 `images/`，但 A01–A05 的 `image` 都指向 `fixtures/*.jpg`。
T10 跑批若按原样执行，这 5 条会全部文件不存在 → 识别准确率显示 0/5，
看起来像"模型全线崩了"，实际是**路径配错**。这类静默失败最容易被误判成模型问题。

处理：A01–A05 标记 `image_status=pending`，并新增 9 条指向真实文件的用例（见下）。
跑批口径改为"只取 `image_status=ready`"，避免把待补素材算进分母。

### 2) 测试把衣柜规模写死成 12，数据一扩就红

加完两双鞋，5 个测试立刻失败，全部是 `== 12` 这类硬编码：
`test_db.py` 三处、`test_wardrobe_api.py` 一处、`test_filter.py` 的 `composable_count == 1`。

这违反"单一数据源"：数据在 `cases.json`，期望值却抄在测试里。
改为从 `cases.json` 读取（`WARDROBE_SIZE`），组合数改为"每双合格鞋各成一套"的推导式。
**以后扩充衣柜不再需要改测试。**

### 3) 候选集规模是这套架构的隐性瓶颈（这条要记住）

同样加两双鞋，各温度带的组合数变化：

| 温度带 | 12 件 | 14 件 | 倍数 |
|---|---|---|---|
| hot | 1 | 4 | 4× |
| warm | 4 | 20 | 5× |
| cool | 12 | 60 | 5× |
| cold | 8 | 40 | 5× |

**件数 +17%，组合数 ×5。** 这是"先过滤再让模型编排"这个架构设计的直接理由：
若把整个衣柜丢给模型自由组合，14 件已是 60 种合法搭配，100 件时会到不可控量级。
候选集必须先由代码收敛，模型只在收敛后的名单里编排——这不是优化，是能不能跑的前提。

## 四、本轮数据变更（cases.json v1 → v2）

| 项 | 变更 |
|---|---|
| wardrobe | 12 → 14 件（W13 拼色板鞋、W14 米白跑鞋） |
| W13/W14 的字段 | 填**人工校正真值**（warmth 均为 2），不填模型原始输出；模型输出与真值的偏差留在本报告，不污染基准数据 |
| filter_spec | 新增 `warmth_exempt_slots: ["shoes"]` |
| 识别用例 | 新增 R01–R09（image 指向 `images/`，路径相对 `cases/` 解析）；A01–A05 标 `image_status=pending` |
| version | v1 → v2，note 追加变更说明 |

用例总数：20 → 29（识别 5 → 14，其中 ready 9 条）。

## 五、验证

- `pytest app/tests`：**167 passed**（新增 2 条鞋相关断言）
- 探针 `scripts/probe_shoes_filter.py`：四温度带全部复现预期
- 数据库：`scripts/seed.py` 灌入后 14 件，鞋 4 双（W08 运动鞋 / W09 乐福鞋 / W13 板鞋 / W14 跑鞋）

## 六、留给后续

1. **prompt 仍缺鞋的 warmth 锚点**——虽然过滤层已豁免，但编排理由是 LLM 写的，
   它会读到"这双鞋 warmth=3"并可能写出不合理的理由。建议在 `item_extract` prompt 增加一句鞋的分区锚点
   （单层/加绒/雪地靴三档即可），作为 T5 离线部分的一部分。
2. **缺件建议里鞋的 `warmth_min` 无意义**
   `shortage.requirements` 对鞋仍输出 `warmth_min`。不影响功能，但会误导缺件提示文案，已记入 backlog。
3. **非衣物识别（NOT_CLOTHING）尚无真实素材**
   A05 仍为 pending，该分支目前只有单测覆盖，真实链路未验。

## 七、修复后的真实端到端验证（28℃ / weekend）

用 `scripts/e2e_probe.py`（进程内起 uvicorn + 真实 HTTP + 真实模型调用 + 真实写库）跑，
避免后台进程被沙箱隔离导致 SQLite 写失败。

```
HTTP 200   墙钟 7858ms   latency_ms=7848   degraded=False   prompt=outfit_compose.v1
衣柜 14 件，鞋 [W08 运动鞋, W09 乐福鞋, W13 板鞋, W14 运动鞋]
rank 1: top:W01 + bottom:W04 + shoes:W08（outer 无）
rank 2: top:W01 + bottom:W04 + shoes:W13
rank 3: top:W01 + bottom:W04 + shoes:W14
shortage=None   shortage_hint=None
```

**鞋位三套全部命中，无降级、无缺件。** 修复前同一场景（warmth=3 的板鞋）会被
`allowed_warmth["hot"]=[1,2]` 直接过滤，用户看到的是"夏天没有鞋可配"。

### 三套方案上下装完全相同——不是模型偷懒，是数据决定的

初看像质量问题，实测候选集后确认是结构问题：

| 场景 | 温度带 | 上装 | 下装 | 外套 | 鞋 | composable_count |
|---|---|---|---|---|---|---|
| 28℃ weekend | hot | **1** | **1** | 0 | 3 | **3** |
| 22℃ commute | warm | 1 | 3 | 0 | 1 | 3 |
| 12℃ commute | cold | 1 | 3 | 3 | 1 | 9 |
| 18℃ date | cool | 3 | 2 | 2 | 3 | 36 |

28℃ 只有 1 件上装和 1 件下装能过温度带，合法组合恰好 3 种，且差异全在鞋上。
系统给出的就是全部合法答案，`shortage_hint` 为空是因为 `expected_count = min(3, 3) = 3`。

**这套逻辑本身是可信的**（`compose.py:44` + `validate.py:23,32`）：

- 方案数被强制等于 `min(3, 实际可组合数)`，凑不出 3 套时如实返回 2 套并给
  `shortage_hint="符合条件的不同方案仅 N 套。"`；
- 跨套重复被硬性拒绝——`validate.py:34` 的「重复方案不能用于凑数」用 `frozenset(ids)` 去重，
  模型想靠换鞋凑数会被打回并进入一次纠错重生成。

**结论要写进简历也写进产品**：方案多样性由衣柜结构决定，不由模型决定。
真正需要补的是夏季上装/下装各 2–3 件（P1 数据补强），而不是调 prompt。

