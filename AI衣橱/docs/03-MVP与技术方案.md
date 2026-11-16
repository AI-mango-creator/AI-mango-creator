# 03 · MVP 范围与技术方案（基线）

> **这份是「基线」，不是「定稿」。** 阶段 2 的任务是让 Codex 基于它细化、挑错、补漏；如果你发现 Codex 的产出比这份差，说明它没读进去，重来。
> 标 🔒 的是**已经定死的决策**（改了会影响验收），标 ⬜ 的是留给 Codex 发挥的。

---

## 一、范围三层

### P0 · 必须做完才能演示

| 序号 | 能力 | 用户可见结果 |
|---|---|---|
| 1 | 建档：拍照上传 6–10 张，批量识别成单品卡片 🔒 | 3 分钟内看到自己衣柜变成一列卡片 |
| 2 | 建档兜底：识别失败可手动改品类/主色 🔒 | 一张卡最多改 2 项就能用 |
| 3 | 场景选择：温度带（4 档）+ 场合（通勤/约会/周末/会议）🔒 | 两个滑选，3 秒完成 |
| 4 | 生成方案：3 套，含单品拼贴 + 一句话理由 🔒 | 30 秒内看完并选定一套 |
| 5 | 换一套 / 这件不想穿 🔒 | 点击后 5 秒内出新方案，且确实不同 |
| 6 | 缺件提示：候选不足时如实说明缺什么 🔒 | 「你只有 1 件外套，8℃ 建议加一件厚外套」 |
| 7 | 降级明示：AI 失败时顶部黄条 + 规则模板方案 🔒 | 不白屏，且知道自己看到的是降级结果 |

### P1 · P0 完成后有余力才做

| 优先级 | 能力 | 为什么这个顺序 |
|---|---|---|
| P1-1 | 买前试配（候选单品 → 覆盖率报告） | 差异化最强、且完全本地闭环；但依赖 P0 衣柜数据成型 |
| P1-2 | 天气 API（按定位取气温） | 体验提升明显，但引入权限/城市映射/失败重试，2 天成本 |
| P1-3 | 历史记录（"上周穿过这套"）+ 3 天去重 | 让"每天都用"成立，但要处理跨天状态 |
| P1-4 | 理由可点开，看属性来源 | 增强可信度，纯前端工作 |

### Out of Scope（明确不做）

| 不做 | 原因 | 如果非要做得先解决 |
|---|---|---|
| 3D 人体建模 / 虚拟试穿 | 需专用模型或付费 API + 渲染管线，与"30 秒决策"无因果 | 有稳定的 3D API 预算 + 单机渲染方案 |
| 电商链接抓取 | 反爬 + 合规风险，且页面结构周周变 | 官方开放平台授权 |
| 退货率 / 商家信用分 | 无数据源，只能编数字 | 有真实订单数据 |
| 用户体系 / 多端同步 | 单机 MVP 无需，且会拖慢所有接口 | 有明确的多设备需求 |
| 社交分享 / 社区 | 冷启动无内容，无法验证 | 有种子用户 |
| 会员付费 / 积分 | 无留存谈不上付费 | 有留存数据 |
| 多语言 / 深色模式 / 无障碍 | 与核心链路无关 | 上线后按需 |
| 语音输入 | 输入已经够快（两个滑选），语音是负优化 | 输入步骤 > 3 时再考虑 |

---

## 二、数据模型（🔒 四张表，字段可增不可减）

> 铁律：每个字段必须能标注来源 —— `user`（用户输入）/ `model`（模型产出）/ `derived`（代码计算）。三者混在一起，后面必然出现"置信度是用户填的"这类荒唐设计。

### `wardrobe_items` — 衣柜单品

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| id | TEXT PK | derived | `W01`… |
| image_path | TEXT | user | 本地 `data/uploads/` 相对路径 |
| category | ENUM(top/bottom/dress/outer/shoes/accessory) | model | 大品类 |
| sub | TEXT | model | 子类：衬衫/西裤/乐福鞋… |
| colors | JSON array | model | 主色 + 辅色 |
| material | TEXT | model | 棉/羊毛/牛仔… |
| pattern | TEXT | model | 纯色/条纹/碎花 |
| warmth | INT 1–5 | model | 厚薄，**保暖层的判定依据** |
| formality | INT 1–5 | model | 正式度，1 家居 / 5 正装 |
| seasons | JSON array | model | spring/summer/autumn/winter |
| confidence | FLOAT | model | 0–1，<0.7 进待确认 |
| needs_confirm | BOOL | derived | 是否待用户确认 |
| user_edited | BOOL | derived | 用户是否改过，改过则 confidence 置 1.0 |
| created_at | DATETIME | derived | |

### `outfit_sets` — 一次生成的一套方案

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| id | TEXT PK | derived | |
| session_id | TEXT FK | derived | 同一次请求的 3 套共享 |
| rank | INT | derived | 1/2/3 |
| reason | TEXT | model | 一句话理由，须引用真实属性 |
| shortage_hint | TEXT NULL | derived | 该套的缺件说明 |
| degraded | BOOL | derived | 是否来自降级模板 |

### `outfit_items` — 方案与单品的多对多

| 字段 | 类型 | 来源 |
|---|---|---|
| set_id | TEXT FK | derived |
| item_id | TEXT FK | model 选出、derived 校验 |
| slot | ENUM(top/bottom/outer/shoes/dress/accessory) | model |

> 唯一索引 `(set_id, slot)`：**同一套里一个位置只能放一件**。这条索引本身就是 C05 那个 bug 的防线。

### `sessions` — 一次请求

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| id | TEXT PK | derived | |
| temp_c | INT | user | |
| occasion | ENUM(commute/date/weekend/client_meeting) | user | |
| formality_target | JSON [min,max] | derived | 由 occasion 映射 |
| excluded_items | JSON array | user | 用户排除 |
| status | ENUM(ok/degraded/failed) | derived | |
| fallback_type | TEXT NULL | derived | timeout / parse_fail / no_compliant_set |
| latency_ms | INT | derived | |
| prompt_version | TEXT | derived | 用于复盘"是不是换 prompt 导致的" |

---

## 三、API 契约（⬜ Codex 可调路径名，但错误码语义不可改）

| Method | Path | 入参 | 出参 | 错误码 | P95 |
|---|---|---|---|---|---|
| POST | `/api/wardrobe/upload` | 多文件 | `{items:[WardrobeItem], rejected:[{reason}]}` | 400 / 415 | 6s |
| PATCH | `/api/wardrobe/items/{id}` | `{sub?,colors?,category?}` | `WardrobeItem` | 400 / 404 | <100ms |
| GET | `/api/wardrobe/items` | — | `[WardrobeItem]` | — | <200ms |
| POST | `/api/outfits` | `{temp_c, occasion, excluded[]}` | `{session_id, sets:[OutfitSet], degraded, hint}` | **400** 参数错 / **422** 无合规方案 / **504** 模型超时 / **500** 其他 | 12s |
| POST | `/api/outfits/{session_id}/reroll` | `{keep_set_ids[]}` | 同 POST /outfits | 同左 | 8s |

**422 是这条链路最重要的错误码**：它表示"我算过了，你的衣柜确实配不出 3 套"，必须携带 `shortage_hint`，前端要渲染成"缺件建议"而不是错误页。**没有 422 的方案一定是没想清楚 P4。**

---

## 四、页面清单（5 页，不能再多）

| # | 页面 | 一句话职责 | 必须有的三态 |
|---|---|---|---|
| 1 | 首页 | 一个大按钮「今天穿什么」+ 衣柜件数 | loading：骨架屏；empty：衣柜 0 件 → 引导建档；error：后端不可达 → 重试 |
| 2 | 建档页 | 上传照片 → 识别进度 → 可编辑卡片墙 | loading：逐张进度条；empty：未选图 → 提示；error：单张失败 → 只标记该张，不整批失败 |
| 3 | 场景页 | 温度带 4 选 1 + 场合 4 选 1 + 排除 | loading：无；empty：无（必有默认值）；error：无 |
| 4 | 方案页 | 3 套卡片 + 换一套 + 缺件提示 + 降级黄条 | loading：3 个占位卡；empty：422 → 缺件建议卡；error：黄条 + 基础方案 |
| 5 | 我的衣柜 | 卡片墙 + 待确认标记 + 删除 | loading：骨架；empty：引导建档；error：重试 |

**视觉**：沿用 PRD 第 32 页规范 —— 主色浅蓝 + 米色，风险橙、适配绿，375px 起。

---

## 五、一次请求的时序（🔒 降级点必须在这里）

```
客户端                后端                        模型
  │  POST /api/outfits   │                          │
  ├─────────────────────>│                          │
  │                      │ 1. 参数校验（代码）        │
  │                      │ 2. 取衣柜 items           │
  │                      │ 3. S2 过滤（纯代码，无模型）│
  │                      │    └ 候选 < 3 件 → 直接 422 + 缺件提示
  │                      │ 4. S3 编排 ──────────────>│
  │                      │    timeout=20s, retry<=2  │
  │                      │<──────────────────────── │
  │                      │ 5. S4 校验（纯代码）       │
  │                      │    衣柜内？同套重复？温度冲突？
  │                      │    └ 失败 → 带错误原因重生成 1 次
  │                      │ 6. 仍失败 → 规则模板兜底   │
  │<─────────────────────│    degraded=true          │
  │  渲染 3 张卡 / 缺件卡  │                          │
```

**降级从第 4 步开始，不在第 1–3 步**。第 1–3 步是纯代码，失败说明有 bug，应该报错而不是降级 —— 否则 bug 会被"降级"掩盖，永远查不出来。

---

## 六、两个 Prompt 的设计要点（⬜ 文案由 Codex 写，结构不可改）

### `prompts/vision_extract.v1.md`

- 输入：一张图（可能多件叠放）
- 输出：`{items:[{category,sub,colors,material,pattern,warmth,formality,seasons,confidence,bbox}]}`
- 硬要求：**必须给 confidence**；看不清就把 confidence 打低，**禁止猜**；非衣物返回 `items: []`
- 禁止：输出"建议搭配"，这不归它管

### `prompts/outfit_compose.v1.md`

- 输入：候选集（**已经过代码过滤**，12 件基准衣柜实测 5–9 件，真实 70 件衣柜约 15–25 件）、温度、场合、正式度区间
- 输出：`{sets:[{item_ids:[], reason}]}`，恰好 3 套
- 硬要求：
  1. **只能从候选集里选**，item_id 不在候选集里视为失败
  2. 每套必须齐 `top + bottom + shoes`（`dress` 可替代 top+bottom）；`temp_c < 20` 时必须有 `outer`
  3. 同一套内一个 slot 只能一件
  4. reason 必须引用至少一个真实属性（温度/正式度/颜色），**不许写"显瘦""气质"这类无法核对的词**
  5. 候选集配不出 3 套时，**返回 `{sets:[], shortage:"..."}`**，不要凑
- 温度：0.3（要有一点多样性，否则 B10 的「换一套」失效）

---

## 七、任务清单模板（阶段 3 让 Codex 填满，这里给前 6 个示范）

| 任务 | 描述 | 涉及文件 | 验收方式 | 估时 | 依赖 |
|---|---|---|---|---|---|
| T1 | 骨架 + Makefile + 前端 hello 页 + 后端 /health | Makefile, app/main.py, web/src/App.tsx | `make dev` 后 curl /health 返回 200；浏览器 375px 打开有页面 | 0.5d | — |
| T2 | 数据模型 + SQLite 建表 + seed 灌 12 件 | app/models.py, app/db.py, cases/wardrobe.json | `make seed` 后 `sqlite3 data/app.db "select count(*) from wardrobe_items"` = 12 | 0.5d | T1 |
| T3 | 手动建单品接口 + 衣柜页卡片墙 | app/routers/wardrobe.py, web/src/pages/Wardrobe.tsx | 页面新增一件后刷新仍在；空态显示引导 | 1d | T2 |
| T4 | S2 过滤 + 单测（覆盖 B02/B05/B07/B08 四类断言） | app/services/filter.py, tests/test_filter.py | `pytest tests/test_filter.py` 全绿；`make eval` 的 B07/B08 从失败转通过 | 1d | T2 |
| T5 | S1 识别接口（含 A05 拒绝路径） | app/services/extract.py, prompts/vision_extract.v1.md | 传咖啡杯图返回 422 NOT_CLOTHING；传衬衫返回 confidence>0.8 | 1d | T2 |
| T6 | S3 编排 + S4 校验器 + C05 拦截 | app/services/compose.py, validate.py, prompts/outfit_compose.v1.md | 注入重复上装 → 校验器拒绝并重生成；`make eval` 组合类 ≥7/10 | 1.5d | T4 |

> 注意 T4 排在 T5 前面：**先把纯代码的过滤跑通，再接模型**。反过来的话，模型一报错你就分不清是模型问题还是过滤问题。这是本项目的排序原则。

---

## 八、技术选型的两句话理由（面试会问）

- **为什么 Web 而不是原生 App / 小程序**：同一套代码手机浏览器直接开，面试时发个链接就能看；PWA 可加到桌面，体验损失可接受。原生 App 要审核、要装包、要处理签名，全是与核心链路无关的成本。若后续必须进微信生态，`web/` 的页面结构可平移为小程序，后端不动。
- **为什么 SQLite 而不是 Postgres**：单用户、数据量百级、需要"clone 下来就能跑"。SQLite 让面试官在你电脑上 30 秒内跑起来，这比任何技术先进性都重要。

---

## 附录 · P2 演进路径与未采用理由

### 本轮模型分层定稿（2026-11-12）

- **P0：只走 API，只允许 2 次模型 API 调用。** 识别使用一个多模态 VLM，编排使用一个文本 LLM，可来自同一家服务。规则过滤、硬约束校验和规则降级不调用模型。不得用隐藏重试或额外模型步骤突破调用预算。
- **识别契约**：输入照片，输出 `{items:[{category,sub,colors,material,pattern,warmth,formality,seasons,confidence,bbox}]}`；必须提供 `confidence`，看不清则降低置信度，非衣物返回 `{items:[]}`。
- **编排契约**：输入经过规则过滤的候选集，输出 3 套及可核对的理由；遵守已确认的 P4 决策，只有 1–2 套合规方案时如实少出，无合规方案时明确说明，不硬凑。
- **运行边界**：当前设备为 16GB MacBook Air；P0 禁止下载任何模型权重，禁止引入 Paddle、SAM、detectron2、diffusers 或 GPU 依赖。
- **P1：P0 验收通过后，虚拟试穿仅采用托管推理 API，不自建。** 本轮只记录分层，不实施试穿；实施前须单独同步 `AGENTS.md` 中的范围约束，不能将试穿并入当前 T1。
- **P2：下表六项仅作演进记录，不下载、不安装、不实施。**

### 未采用的共同原因

检测 → 分割 → 分类 → 属性四段串联会累积误差：下游字段错误可能来自上游漏检、裁切丢失或分类错误，仅看最终结果难以归因。串行延迟也会累加；若四段耗时相近，可近似为单段延迟乘四，这是设计估算而非实测数据。该路线与建档处理总耗时 ≤90s 存在冲突风险，也增加当前 16GB 设备的部署负担，因此不作为 P0 路线。

### 能力、未采用理由与切换门槛

以下数字是**启动切换评估的门槛**，不是已测结果，也不替代或降低 `docs/04-验收标准与失败处理.md` 的验收线。识别比较使用同一批 10 张人工标注真实衣柜照片；字段命中率为正确字段数 / 人工可判定字段总数，漏检对应字段计错。候选路线必须在同一批照片上复测，识别路线须保持建档处理 ≤90s；满足门槛不代表自动切换，更不授权 P0 增加模型调用。

| 能力 | 未采用理由 | 触发切换的条件 |
|---|---|---|
| **PP-YOLOE+ 定位**：检测衣物位置，提供单品框 | 增加独立检测阶段；漏检会让后续属性提取失去输入；P0 禁止 Paddle 与本地权重 | P0 可见衣物检出率 <80%，人工归因确认主要是漏检；候选检测方案在同批照片上检出率 ≥90%，且新部署设备或托管服务已可用 |
| **SAM 2.1 抠图**：从单品区域提取前景掩码 | 增加分割阶段且依赖定位输入；P0 只需缩略图拼贴，不以精细抠图作为出方案前提 | 已正确定位的单品裁片中，超过20%因混入相邻衣物而被人工判为不可用；候选分割方案将该比例降至 ≤10%，且托管服务或新部署设备已可用 |
| **PP-LCNet 分类**：判断单品品类 | 与 VLM 的 category/sub 输出重叠；额外分类不能补回漏检，也会引入新的分类错误；P0 禁止 Paddle | 在正确定位单品上，P0 category 字段命中率 <80%，且候选分类方案同批命中率 ≥90%；托管服务或新部署设备已可用 |
| **Qwen2.5-VL 本地部署**：本地完成视觉属性提取 | 当前设备为16GB MacBook Air；本地权重和推理环境超出 P0 的 API 路线 | 连续20次真实 API 识别请求中失败率 >10%，且已具备其他部署设备；候选本地方案实测字段命中率 ≥80%、10张处理 ≤90s，并在该设备上完成内存占用验证 |
| **SCHP+DensePose**：人体区域解析及身体表面对应 | 服务于人体解析/试穿，不属于衣柜单品识别主链路；串联解析模块会增加误差来源与延迟 | P1托管试穿在20个已获用户授权的样本中，人体/衣物区域错位率 >20%，且人工归因确认问题来自人体解析；同时已具备可运行候选方案的托管服务或新部署设备 |
| **CatVTON 自部署**：自建虚拟试穿推理 | P1已定为托管 API；自部署引入权重、算力和维护成本，与当前设备及范围不符 | P1托管试穿连续20次请求失败率 >10%，且已有其他部署设备；候选自部署方案在同批20个授权样本上成功率 ≥95%，P95耗时不高于托管基线；另行批准自建范围后才可实施 |

### 与旧基线尚待同步的冲突

旧正文的重试/校验重生成流程，以及 C03、C05 对重试或重生成的要求，尚未与“2次 API 调用”预算统一。这里保留原文和原 case，不改期望、不宣布通过；实现模型调用前须确定两次预算的统计范围并解决冲突。T1（骨架、`make dev`、`/health`）不调用模型，不依赖该问题解决。

## T13 增量技术契约（2026-11-14）

既有字段保留；运行协议唯一真相仍为models.py。本节是增量，不覆盖旧版本评测口径。

| 对象 | 新字段/规则 | 来源 | 存储约束 |
|---|---|---|---|
| wardrobe_items / sessions / outfit_sets / outfit_items | owner_id | derived：客户端设备UUID经服务端校验，legacy仅迁移/本地工具 | TEXT NOT NULL；HTTP拒绝legacy与缺失UUID；查询/写入/照片/候选均强制owner |
| daily_quotas | owner_hash/day/recognition/composition/expires_at | 全部代码计算；无用户/模型属性混入 | hash=sha256(device_id+服务器盐)，不存UUID；主键hash+day，识别≤20/编排≤30，次日0点到期 |
| 新上传单品 | needs_confirm=true，不再以confidence放行 | derived，D10-b唯一派生函数 | 用户五字段PATCH或显式confirm后解除；confidence始终保留模型值/来源 |
| 对外item_id | 不编码设备UUID | derived | 新上传随机前缀，开发seed盐映射；004幂等迁移旧owned键及引用，legacy原ID不改 |

业务API统一X-Device-ID（有效UUID），缺失/非法400；响应no-store/Vary:X-Device-ID。GET照片也校验归属，前端带头取blob；设备持久化唯一模块deviceId.ts。

新增DELETE /api/wardrobe/items：按owner清四业务表及照片，保留当日匿名计数；新增POST /api/wardrobe/items/{id}/confirm（无属性body）：只确认，不伪造字段编辑，未知id/跨owner404，非法属性body422。配额超限429+中文/Retry-After，等待写锁后再采样日界，内部重试/成功缓存重传不多扣。

历史数据固定归legacy，开发脚本默认dry-run，--apply才认领；make seed默认legacy、新设备不自动灌测试衣柜。清空与写请求使用固定64桶文件锁互斥，不新增队列/缓存服务。完整迁移/回滚/验收见T13报告。
