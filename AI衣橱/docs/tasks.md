# tasks.md — 任务板（唯一进度真相）

> **这份文件是「确定 MVP」这一步的产物。** 范围已经锁在 `docs/decisions.md` D1–D7，本表只管两件事：**做哪些、按什么顺序做、怎么算做完**。
> 规则：一次只推进一个任务；动手前先复述（做什么 / 验收标准 / 碰哪些文件）；完成后回填本表状态与实测证据，再提交。
> 状态没回填＝任务没完成。简历里的进度数字**只能**来自本表的"实测证据"列。

图例：✅ 完成 · 🟡 部分完成 · ⬜ 未开始 · ⛔ 阻塞

---

## 一、当前进度

| 阶段 | 状态 | 说明 |
|---|---|---|
| 阶段 1 需求对齐 | ✅ | `docs/decisions.md` D1–D7 定稿 |
| 阶段 2 方案输出 | ✅ | `docs/03` 数据模型 / API 契约 / 5 页清单 / 时序 |
| **阶段 3 确定 MVP** | ✅ | 本文件（范围锁 P0 七项 + Out of Scope 八项） |
| 阶段 4 项目测试 | ✅ | T10/T11评测交付；失败与缺项保留，人工可穿率未测 |
| 阶段 5 BUG 改进 | 🟡 | T12文档完成；T5上传已验，完整演示待T9换一套 |

**当前任务：T17主页入口修复。已定位根README仍使用旧免费通道且匿名502/no tunnel，当前新通道首页/health200；更新GitHub主页体验按钮并保留其他内容，远端回读验证中。见reports/t17-profile-entry-fix.md。**

**此前T5上传链路✅：D1真实落库门闸后，D2九张真实浏览器上传全部成功，完整单张建档5411–8880ms（n=9）。** 正式九张SQLite15→24，同draft全部重传仍24、模型调用9→9；corrections审计均落库，本批0条。T12仍🟡待T9/完整演示，T11✅；识别稳定性2/3见repeatability报告。134个旧证据/prompt/cases哈希不变。
D2全量244 pytest + 15 Vitest、lint及构建通过；375×812下上传loading/error/成功与衣柜loading/empty已检查，无横向溢出。失败保留File/input/占位/draft_id，原地重试幂等。T9、完整录屏、人工可穿率、首次10张建档总计时与HTTP端到端P95仍未完成；本轮不改旧prompt/cases或评测证据。

---

## 二、总表

| 任务 | 内容 | 主要产出 | 验收命令（可粘） | 估时 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| T1 | 骨架闭环：双服务 + 代理 + 三态 + test/lint 全绿 | `Makefile`、`web/vite.config.ts`、`web/src/App.tsx`、`web/src/lib/viewState.ts`、`web/src/lib/viewState.test.ts` | 见 §3.1、§5 | 0.5d | — | ✅ |
| T2 | 数据模型 + 建表 + seed 12 件 | `app/models.py`、`app/db.py`、`app/migrations/001_init.sql`、`scripts/seed.py`、`app/tests/test_db.py` | 见 §3.2、§5 | 0.5d | T1 | ✅ |
| T3 | 衣柜接口（GET / PATCH）+ 卡片墙页 | `app/routers/wardrobe.py`、`web/src/pages/Wardrobe.tsx` | 见 §3.3、§5 | 1d | T2 | ✅ |
| T4 | **S2 过滤 + 单测**（12 条 filter 层断言：B01–B10 + C01 + C02） | `app/services/filter.py`、`app/tests/test_filter.py` | 见 §3.4、§5 | 1d | T2 | ✅ |
| T5 | 上传/识别/校正入库/卡片全链路，九张真实验收与幂等通过 | `app/services/extract.py`、`app/routers/wardrobe.py`、`web/src/pages/Wardrobe.tsx`、`reports/t5d-upload-chain.md` | 见 §3.5、§5 | 1d | T2 | ✅ |
| T6 | S3 编排 + S4 校验器（含 C05 重复上装拦截）；真实调用已通过 | `app/services/compose.py`、`validate.py`、`app/llm/client.py`、协议模型与版本化 prompt | 见 §3.6、§5、`docs/reports/t6-real-call.md` | 1.5d | T4 | ✅ |
| T7 | 场景输入 + 方案页，首次端到端通过 | `web/src/pages/Outfits.tsx`、`app/routers/outfits.py`、API 协议及页面切换 | 见 §3.7、§5 | 1.5d | T3、T6 | ✅ |
| T8 | 降级与错误码；黄条接入及截图已随 T7 完成 | `app/services/fallback.py`、`app/llm/errors.py`、`web/src/components/DegradeBanner.tsx` | 见 §3.8、§5 | 1d | T6 | ✅ |
| T9 | 换一套（reroll）+ 排除单品 | `app/routers/outfits.py`、`web/src/store` | 见 §3.9 | 0.5d | T7 | ⬜ |
| T10 | **评测跑批 v1**：24条可跑 + 5条素材未备显式跳过 | `scripts/evaluate.py`、`docs/reports/eval_v1.md`、原始响应 | 见 §3.10、§5 | 1d | T6 | ✅ |
| T11 | 评测口径收尾；识别稳定性 2/3，见 repeatability 报告（R02/R03各n=3） | `docs/reports/eval_v3.md`、`raw/*_v3/`、`t11-repeatability.md` | 见 §3.11、§5 | 1d | T10 | ✅ |
| T12 | 五项作品说明与简历/README已补齐；T9/完整录屏缺项保留 | `docs/作品说明.md`、`docs/05-简历文案.md`、`README.md`；demo未创建 | 见 §3.12、§5 | 0.5d | T11 | 🟡 |
| T13 | 上架前必修：A隔离/匿名配额/清空→B上传确认→C文案；含审查修复及九张真实验收完成 | `docs/07-T13实施计划.md`、`reports/t13-data-isolation.md` | 分段全量pytest后继续 | — | T5 | ✅ |
| T14 | 部署就绪配置已在codex/t14-ready准备，容器未构建验证，尚未合入main | 独立T14分支 | 等Docker环境就绪补build/run | — | T13 | 🟡 |
| T15 | 单品硬删除与方案图片预览：共用照片最后引用清理、照片失败降级与资源释放 | `app/routers/wardrobe.py`、`web/src/components/ItemPhoto.tsx`、`reports/t15-experience.md` | make test/lint/build；CDP375×812 | — | T3、T7 | ✅ |
| T16 | 临时HTTPS真实交互测试：同址网页/API、独立库、全站20/30日额度、真实上传/确认/生成；带宽限制披露 | `scripts/share.py`、`app/tests/test_share.py`、`docs/10-临时测试指南.md`、`reports/t16-share.md` | make share；公网health/上传/生成/隔离；make test/lint | — | T5、T7、T13、T15 | ✅ |
| T17 | GitHub主页公开完整项目快照及源码入口，保留首页原内容 | [AI衣橱源码](https://github.com/AI-mango-creator/AI-mango-creator/tree/main/AI%E8%A1%A3%E6%A9%B1) | 远端递归tree对比本地Git blob SHA和mode；make test/lint | — | T16 | ✅ |
| T18 | 身材资料、五体型示意、推荐说明接入及衣橱管理分类；按A—E实施 | docs/11-资料与分类实施计划.md、reports/t18-profile-categories.md | 每段make test/lint；最终375×812 | — | T17 | ✅ |
| T19 | 参考图首页、真实城市天气与详情视觉改版；A→B→C | docs/superpowers/specs/2026-11-18-home-weather-design.md | 分段make test/lint，最终CDP375×812与真实天气 | — | T18 | ✅ |
| T20 | 真实社区：四类发布/关注/点赞/评论/投票，衣橱与搭配导航合并；A—E及双设备验收完成 | docs/reports/t20-community.md | 分段test/lint、双设备真实API与375×812 | — | T19 | ✅ |
| T21 | 首页服饰体验目录、详情与真实托管试穿；先体验版后平台接入 | docs/superpowers/specs/2026-11-19-tryon-experience-design.md | 分段全量test/lint，375×812，真实试穿需另确认资源与预算 | — | T19、T20 | 🟡 |
| T22 | 我的中心、真实每日积分/互动/设置/收藏与私密OOTD，A—F及审查修复/移动端验收完成 | docs/reports/t22-personal-center.md | 409 pytest+76 Vitest、lint/build；双设备HTTP、26图375×812 | — | T18、T20、T21离线 | ✅ |

**关键路径**：T1 → T2 → T4 → T6 → T7 → T10 → T11 → T12（这条路径决定"什么时候有验收证据"）。
T5 可以并行，但**按纪律串行**；T3 只为 T7 服务，不要提前做卡片墙美化。

---

## 三、逐任务验收（命令照抄，不许"目测通过"）

### 3.1 T1 · 骨架闭环
```bash
make dev          # 一条命令同时起 :8000 与 :5173，Ctrl-C 一起退出
curl -s localhost:8000/health                                  # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" localhost:5173/       # 200
make test         # exit 0（pytest + vitest 都跑了，不是"跳过"）
make lint         # exit 0（ruff + tsc --noEmit）
cd web && npm run build   # exit 0
```
人工：375×812 下 hello 页三态各截一张图（loading / empty / error），无横向滚动。

**T1-0 本轮范围（不改变上述完整 T1 标准）**：

- `getViewState` 接收 `status` 与 `itemCount`；依次处理 loading、error，再由件数判定 empty/ready。`status` 为互斥枚举，测试不会伪造同时 loading 与 error 的非法输入。
- `main.tsx` 保持不动；App 默认 `status='ok'`、`itemCount=0`，ready 显示「共 N 件」。
- 仅开发环境支持 `/?state=loading`、`/?state=error`，`/` 为默认 empty；不临时改默认值截图。人工可在仓库根目录运行 `cd web && npm run dev`，再访问 `http://127.0.0.1:5173/` 及上述查询参数。生产构建移除读取查询参数的预览代码。
- 前端仅新增 `vitest@5.1.0`，无 DOM 环境、无覆盖率包、无 `@types/node`；未修改旧锁条目、已有安装包版本、engines、`main.tsx` 或 `tsconfig.json`。
- 依赖单独提交；实现与脚本另行提交。开发预览入口已提供，但本轮未宣称三态截图或人工验收通过。

**T1 收尾本轮范围**：只改 `web/vite.config.ts`、`Makefile`、`CHANGELOG.md`、本文件；不改 App/main、不安装依赖。`make dev` 用 shell trap 清理两个服务并等待退出；前端直接启动已有 Vite，`/api` 请求原样代理到 `http://127.0.0.1:8000`，不移除前缀、不补后端路由。

人类验收入口：仓库根目录执行 `make dev`，在 375×812 下分别访问 `http://127.0.0.1:5173/?state=loading`、`http://127.0.0.1:5173/`、`http://127.0.0.1:5173/?state=error`。**三态截图待人类验收**。

> **截图坑（T7 起每个页面都要用，务必记住）**：无头 Chrome 的 `--window-size=375,812` 会被夹到最小 500px 宽（实测 `innerWidth=500`），截出来的 375 宽 PNG 其实是 500px 视口的左侧裁切，看起来"右侧被切掉"，但页面本身没溢出。
> 正确做法是用 CDP 的设备模拟：`Emulation.setDeviceMetricsOverride({width:375,height:812,deviceScaleFactor:2,mobile:true})` 再 `Page.captureScreenshot`；验收数值读 `document.documentElement.scrollWidth`，必须等于 375。
> 用 Chrome 手动截时，开发者工具（`⌘⌥I`）→ 设备工具栏（`⌘⇧M`）→ Responsive 填 375×812，效果等价。

### 3.2 T2 · 数据模型 + seed
执行顺序：先写临时库测试并确认失败 → 实现 Pydantic 模型及字段来源 → 添加四表初始化迁移与幂等 seed → 逐条运行 CLI 验收及全量 test/lint → 再查真实库仍为 12 → 回填证据并提交。只读 `cases/cases.json` 的 wardrobe，不复制衣柜数据、不进入 T3/T4。

```bash
make seed
sqlite3 data/app.db "select count(*) from wardrobe_items;"      # 12
sqlite3 data/app.db ".schema outfit_items" | grep -i unique      # UNIQUE (set_id, slot)
sqlite3 data/app.db "select category,count(*) from wardrobe_items group by category;"
make seed && sqlite3 data/app.db "select count(*) from wardrobe_items;" # 仍为 12
make test                                                        # 新增 test_db.py 仍全绿
make lint                                                        # exit 0
sqlite3 data/app.db "select count(*) from wardrobe_items;"       # 测试结束后仍为 12
```
判据：四表定名 `wardrobe_items` / `outfit_sets` / `outfit_items` / `sessions`，保留 `docs/03` §2 全部字段；`sources` TEXT 列保存字段名到 user/model/derived 的 JSON 映射。来源默认值由 `app/models.py` 的字段元数据生成，验证一个模型选择的 ID 不会将其来源改成 derived。

T2 实现说明：

- 唯一衣柜源是 `cases/cases.json` 的 wardrobe；不创建 wardrobe.json、不修改原始字段值。额外的 `name` 列保留原有名称，缺失的 `image_path` / `confidence` 为 NULL，不伪造图片或模型置信度。
- 每次连接启用外键；`outfit_items` 的 `UNIQUE (set_id, slot)` 拦截同套两个上装，外键阻止写入不存在的衣柜 ID。四张表均有 sources 列，模型中枚举使用 Literal。
- 001 只执行事务内的 `CREATE TABLE IF NOT EXISTS`；不删表、不删列。seed 先做 Pydantic 校验，再以 `ON CONFLICT(id) DO NOTHING` 插入，因此重复执行不会新增重复项或覆盖用户修改。
- `test_db.py` 的库路径全部来自 pytest `tmp_path`，包括 CLI 子进程的 `--database` 参数。测试覆盖属性保真、幂等、用户修改保留、四表与模型字段一致性、来源、唯一槽位、外键、非法类型、未知属性 NULL 及中文失败文案；未读写真实 data/app.db。
- sources 字段名和值枚举由 Pydantic 校验；SQLite 的 sources CHECK 验证 JSON 对象形状，不宣称直接 SQL 写入也受 Pydantic 校验。

### 3.3 T3 · 衣柜接口 + 卡片墙
```bash
curl -s localhost:8000/api/wardrobe/items | head -c 300
curl -s -X PATCH localhost:8000/api/wardrobe/items/W01 \
  -H 'content-type: application/json' -d '{"sub":"白衬衫"}' -w "%{http_code}\n"   # 200
curl -s -X PATCH localhost:8000/api/wardrobe/items/W99 \
  -H 'content-type: application/json' -d '{"sub":"x"}' -w "%{http_code}\n"        # 404
curl -s -X PATCH localhost:8000/api/wardrobe/items/W01 \
  -H 'content-type: application/json' -d '{"warmth":9}' -w "%{http_code}\n"     # 422
```
人工：刷新后修改仍在；衣柜 0 件时显示引导而不是空白。

T3 实施口径（2026-11-13，按人类批准范围及 D8）：

- 八个代码文件：`app/main.py` 注册路由/中文错误；`app/models.py` 定义 PATCH 请求和唯一确认派生函数；`app/routers/wardrobe.py`；`app/tests/test_wardrobe_api.py`；`web/src/App.tsx` 接线；`web/src/pages/Wardrobe.tsx`；`web/src/lib/api.ts`；`web/src/lib/api.test.ts`。不新建 wardrobeView、初始化包、依赖或迁移，不改 cases 及已有测试。
- GET 返回 `WardrobeItem[]`，全部字段与 sources 对齐模型；PATCH 仅接受 `sub/colors/material/pattern/category`，其余字段及空请求、错误类型、非法品类均 422。写事务只更新本次字段、对应 user 来源及两个 derived 标记；保留 confidence、warmth、formality、seasons 等原值，404/422/500 只返回中文可读 detail。
- `derive_needs_confirm(confidence, user_edited)` 只在 models 定义，规则为 `(confidence is None or confidence < 0.6) and not user_edited`。PATCH 经统一模型方法置 user_edited 后调用，不直接赋 False。读取保留既有存储标记，不因历史 seed 缺 confidence 而把整个衣柜重新标成待确认。新增临时库测试验证 confidence=0.4 待确认单品从过滤排除到 PATCH 后可参与过滤，且 confidence 仍为 0.4。
- 前端通过 Vite 代理读写真实后端，无 mock/预览开关；使用原 getViewState，error 有重新加载按钮，empty 有准备品类/主色的引导且明确拍照入口尚未开放。卡片显示品类/子类/颜色、待确认及已编辑标记；表单只暴露五个白名单字段。保存失败保留输入，成功用服务端结果更新列表并给顶部提示，刷新重新 GET 验证持久化。暂无图片的基准单品显示「暂无照片」，不伪造图片。
- 三态截图为 CDP `Emulation.setDeviceMetricsOverride({width:375,height:812,deviceScaleFactor:2,mobile:true})` + `Page.captureScreenshot`，不使用 --window-size。仅测试浏览器通过 Fetch 注入 pending/空数组/503 来复现 loading/empty/error，不清空真实数据库；随后解除注入验证真实 12 件、重试、编辑保存与刷新。图片位于 `docs/reports/ui-t3/{01-loading,02-empty,03-error}.png`，均为 750×1624（375×812@2x）。
- 现场异常如实记录：复用此前常驻 dev 时 PATCH 曾间歇 500；相同代码新进程可正常返回。旧进程阶段也出现过连续 10 轮 W01=200/W99=404，随后浏览器仍遇到保存失败；重启本项目 make dev 后完整 curl 和浏览器验收通过。旧进程异常日志未取得，根因未证实，不将此写成已修复的代码 bug。后续复核请从新运行的 make dev 开始，若再现保留后端日志。
  **结案（2026-11-13，人类核查）：间歇 500 是沙箱拦截 SQLite `.db-journal` 删除所致，非代码缺陷；T3 人类验收通过，无需修改业务代码。**

### 3.4 T4 · S2 过滤（纯代码，不调模型）
```bash
.venv/bin/python -m pytest -q app/tests/test_filter.py
make test
make lint
grep -nE "httpx|requests|urllib|llm" app/services/filter.py  # 无输出；grep exit 1 表示无匹配
```
必须覆盖 12 条 filter 层断言（B01–B10 + C01 + C02）。四条重点用例的**准确**含义（此前本节描述为早期草稿，与数据不符，已按 `cases.json` 更正）：

| 用例 | 输入 | 断言的真实含义 |
|---|---|---|
| B02 | 28℃ hot 带 | `must_not_use` W02/W07/W10/W12 —— 外套与冬季上装必须被排除，不是"排除羊毛" |
| B05 | 18℃ cool 带 + 用户排除 W11（半身裙，非半袖） | 被排除单品不得出现，且剩余候选仍可组 3 套 |
| B07 | 26℃（hot 下边界） | 判定必须落在 hot，断言与 B02 相同；与 B08 构成边界对 |
| B08 | 15℃（cool 下边界） | 判定必须落在 cool，此时**必含 outer**，不是"只有夏装返回 shortage" |

必需实现的规则（缺一条就会有 case 挂，且失败原因难以定位）：

1. **`wardrobe_override` 优先**：C02 只给 3 件（W01/W04/W08），过滤必须只在这 3 件里做。忽略它会得到 9 套，与 `set_count_lte=1` 冲突。
2. **`formality_target` 优先于 `occasion_formality`**：input 显式给了就用 input，没给才读 `filter_spec.occasion_formality`。
3. **温度带用区间重叠判定**，不是区间包含；15℃ → cool、26℃ → hot、20℃ → warm、8℃ → cold。
4. **候选不足返回结构化缺件**（含缺哪个槽位 + 建议 warmth 下限），禁止返回空列表、禁止硬凑：C01 无 formal≥4 上装 → 0 套 + shortage；C02 冷天只有夏装 → 0 套 + shortage。

判据：`filter.py` 里**不得出现任何网络调用**，阈值全部来自 `cases/cases.json` 的 `meta.filter_spec`，不许在代码里二次发明数字。
参考基准（人类已用独立模拟器算出，供比对）：B02/B07 → top1/bot3/shoe1/outer0，可组 3 套；B05 → 2/2/1/3，12 套；B08 → 2/3/1/3，18 套；C01 → 0/2/1/1，0 套；C02 → 0/1/0/0，0 套。

T4 实现与验证边界：

- 五项 filter_spec 在模块导入时从唯一案例文件读取并解析；数字阈值未复制到代码。slot_rules 按当前固定文法解析，无法识别时显式报错；规则内容修改后需重新加载进程。
- `filter_candidates` 接收 WardrobeItem 序列与场景字段，返回 `band`、`candidates`、`composable_count`、`shortage`；优先应用 wardrobe_override，显式 formality_target 覆盖场合默认值，排除用户禁用品及待确认/必要属性不明的单品。
- 温度和厚薄/正式度以区间重叠判定，季节取非空交集；outer 的必需/禁止分带、cold 内层 warmth 下限、dress 替代及槽位容量均取自 slot_rules。
- `count_composable_sets(candidates, band)` 在预过滤候选上穷举，按单品 ID 集去重；不读文件、不修改输入、不把配饰变化充作必需槽位组合。完整组合为 0 时返回缺失槽位、warmth_min、formality_min 和中文提示，不返回裸空列表。
- 自动断言直接读原 case 的 input/expect，覆盖其过滤层可行性及数量上下界；精确打印值逐项对照上述人类基准。B03 另验证满足 outer_in / must_use_any_of 的候选仍可组套，未宣称已经编排方案；B09 不验证理由文本，B10 只验证组合池数量，真实换套留给对应任务。

本轮实际打印结果（outer 在 shoes 前；共 12 条）：

```text
case band top bottom outer shoes composable missing_slots
B01 cool 2 3 3 1 18 -
B02 hot 1 3 0 1 3 -
B03 cold 1 3 3 1 9 -
B04 warm 2 2 0 1 4 -
B05 cool 2 2 3 1 12 -
B06 cold 2 2 2 1 8 -
B07 hot 1 3 0 1 3 -
B08 cool 2 3 3 1 18 -
B09 cool 2 3 3 1 18 -
B10 cool 2 3 3 1 18 -
C01 cool 0 2 1 1 0 top
C02 cold 0 1 0 0 0 top,shoes,outer
```

复现上述打印（仓库根目录执行）：

```bash
.venv/bin/python - <<'PY'
import json
from collections import Counter
from pathlib import Path
from app.models import WardrobeItem
from app.services.filter import filter_candidates
source = json.loads(Path('cases/cases.json').read_text())
wardrobe = [WardrobeItem.model_validate(item) for item in source['wardrobe']]
keys = {'temp_c', 'occasion', 'excluded', 'formality_target', 'wardrobe_override'}
print('case band top bottom outer shoes composable missing_slots')
for case in source['cases']:
    if not (case['id'].startswith('B') or case['id'] in {'C01', 'C02'}):
        continue
    result = filter_candidates(wardrobe, **{k: v for k, v in case['input'].items() if k in keys})
    counts = Counter(item.category for item in result['candidates'])
    missing = result['shortage']['missing_slots'] if result['shortage'] else []
    print(case['id'], result['band'], *(counts[s] for s in ['top', 'bottom', 'outer', 'shoes']),
          result['composable_count'], ','.join(missing) or '-')
PY
```

### 3.5 T5 · S1 识别
T5d拆分已批准：D1后端8文件、D2前端3文件顺序提交；D1必须先过一张真实上传并直查SQLite门闸，再进入D2。幂等使用客户端draft_id：重试沿用同ID，成功后复用数据库记录，不重复识别/插入。同ID换图409，未成功时重试可继续。手动入口延期与触发阈值已写backlog，D10未定稿。

当前D1验证：[真实上传门闸](reports/t5d-upload-chain.md)，HTTP201、5708ms，SQLite14→15；再次同draft为200/reused且仍15条。sources保留普通来源标签与_corrections/_upload审计，数据库列和cases属性不变。D2正式九张浏览器样本已通过，完整单张5411–8880ms（n=9）、服务端5277–8761ms；corrections本批0条，来源审计仍逐件落库。同draft九次缓存重传，库24→24、模型调用9→9。详见同一报告的逐张原文、SQLite快照与CDP截图。

```bash
.venv/bin/python -m pytest -q app/tests/test_extract.py
```
判据：传咖啡杯图 → `422 NOT_CLOTHING`；传衬衫图 → `confidence > 0.8` 且字段齐全（9 字段）；模型返回非 JSON → 重试 1 次 → 仍失败走 `IN` 归因并给可读文案。

T5 本轮离线交接（2026-11-13，按最后确认口径）：

- 代码仅 extract.py、batch_extract.py、test_extract.py；原文/summary/prompt 由人类在 `35e18aa` 提供，首批测试误并入该提交的历史不回滚。此轮未改 prompts/*.md、cases.json、client.py 或旧测试，也未用构造响应代替 CSV 的真实来源。
- extract.py 对原 raw_content 剥整段 json/无语言围栏，再 JSON 语法解析并用既有 WardrobeItem 全字段校验；不猜字段、不伪造 confidence。只读原 prompt 文件，逐条检查 sha256 前缀 `148a10064d22f145`、围栏标记及 parsed 与原文一致性。非衣物 items:[] 返回 category=null/reason=NOT_CLOTHING，内部状态码 422；没有在此轮新增上传路由。
- apply_category_rules 返回 `(item, corrections)`，不改输入；outer warmth<2 抬到2，sources.warmth=derived，confidence 原样。seasons 只与现有 filter_spec 允许季节取交集，不另编厚薄阈值，D9 的 shoes 不按 warmth 收窄。真实 R07 seasons 从 `[summer,spring]` 收窄到 `[summer]`，原值、校正值、derived 来源及说明全部输出；R03「长裤」不改写，corrections 只标明 sub 过泛/未命中原断言。
- 跑批只选 image_status=ready 的 R01–R09，用 Semaphore(3) + to_thread 读取/处理原始记录，gather 保持输入顺序；本轮入口是**离线原文重放**，不发请求、不内置 prompt、不提供用假结果顶替实测的 CLI 开关。重放超时预算90s；产品目标仍是10张建档≤90s，当前历史数据是9张并发3墙钟56939ms，不据此声称10张已验收。
- `docs/reports/eval_vision.csv` 固定七列：case_id / 真值 / 实际 / 逐字段一致 / 耗时 / 是否含围栏 / corrections。耗时单位 ms，保留原 latency_ms；实际列同时含 raw/corrected/sources/source=recorded_response。逐字段一致保留录制时的 checks，不对校正结果重评或另定宽松口径，汇总直接读 summary.json，原文与 summary 不一致则中文报错、exit2。
- 运行命令 `.venv/bin/python -m scripts.batch_extract`；原录制用例8/9，所以成功写出完整 CSV 后仍 exit1，明确保留R03真实失败。此退出码是质量结果，不代表回放程序崩溃；缺记录/损坏JSON/hash不符等才是 exit2。未放宽 sub_in 或改成部分匹配。
- 围栏三变体测试使用真实原文：裸JSON取R02，json围栏取R01，无语言分支仅移除R01的语言标记，JSON正文不造；校正/非衣物使用基于原记录的故障注入，不计入实测数字。全量基线167项（含人类D9回归）未改，新增22项。
- 未做新联网识别、上传接口/落库链路、真实非衣物照片和10张完整建档；T5仍🟡。原录制最大单张24888ms超过正式客户端20s限制，未来真实上传接入须按既定超时规则另验，本轮不改超时或prompt以改善数字。无新增页面，本轮没有新的375px人工验收。

### 3.6 T6 · S3 编排 + S4 校验
```bash
.venv/bin/python -m pytest -q app/tests/test_compose.py app/tests/test_validate.py
```
判据：注入"同一套出现两件上装"的响应 → 校验器拒绝并触发重生成 1 次；`reason` 里若出现"显瘦""气质"这类不可核对词 → 判失败。

T6 本轮实施与边界（人类批准的八个代码/配置文件，文档另计）：

- 新增 `compose.py`、`validate.py`、`llm/client.py`、编排 prompt、两份测试、`.env.example`，仅在 `app/models.py` 追加协议模型与派生槽位常量；既有四类持久化模型字段不变，无迁移或 cases 变更，无新增依赖/包初始化文件。
- `Composition.model_json_schema()` 是响应 schema 唯一来源；prompt 模板仅保留 `{{JSON_SCHEMA}}`，不手写 JSON 字段。严格协议中各槽位字段均存在，未使用值为 null；连衣裙替代上/下装保持 D3 决策。校验器从 models 引用槽位定义。
- 默认出口是真实 `client.chat`，没有 mock 开关；离线测试注入脚本响应或 HTTP MockTransport。每次物理请求配置 timeout=20、max_retries=2、temperature=0.3、max_tokens=2048，使用 OpenAI 兼容 Chat Completions JSON Schema 请求；网络重试与一次校验纠错共享三次预算，超时立即停止，失败原因追加为 user 消息。
- C01/C02 的 S2 shortage 直接返回，客户端调用为零；正常目标三套，只有一两套时按 D4 少出并给 shortage_hint。S4 拒绝候选外 ID、槽位/品类错配、缺少/禁用外套、套内重复及指定禁词，复用组合计数检查冷带内层；相同方案不能凑数。无 T8 降级，失败抛带 PARSE/COMPOSE 归因的结构化错误。
- `.env.example` 只有 DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / DASHSCOPE_MODEL 占位。无 key 导入不报错、调用时给中文配置错误；密钥不写入日志或业务返回。每个实际请求记录 case_id、prompt_version、latency_ms、token 数和 degraded=false；未知 token 为 null，不伪造统计。结果耗时覆盖全部重试。
- Prompt diff：此前不存在 → 新增 v1（2026-11-12），增加候选白名单、不同方案数、槽位/温度约束、真实属性与禁词要求、动态 schema 占位；既有 cases 及期望完全未改。32 项离线测试通过，不代表全部评测案例或真实模型通过。
- 未完成：等待人类确认 key 与真实端点/支持 JSON Schema 的模型后单独调用一次并记录实际 latency_ms。理由规则目前只做指定禁词与真实属性命中，不能证明整句语义正确，B09 的 10–60 字尚未验收；真实供应商参数兼容性及整体墙钟超时未验证。本轮不涉及页面，375px 人工检查无新增页面可验。

### 3.7 T7 · 端到端第一次跑通
人工：手动录 5 件 → 选温度与场合 → 出 3 套卡片 → 每套能点开看理由。
判据：**第一次记录端到端耗时**，写进本表"实测证据"列；单次观测不构成P95。本项目现有批次耗时按区间、时段、样本量引用，HTTP端到端P95尚未统计。

T7 本轮实施与验收口径（2026-11-13，人类定稿）：

- 八个代码文件仅 `app/routers/outfits.py`、`app/tests/test_outfits_api.py`、`app/main.py`、`app/models.py`、`web/src/pages/Outfits.tsx`、`web/src/lib/outfitsApi.ts`、`web/src/components/DegradeBanner.tsx`、`web/src/App.tsx`。场景输入与方案展示放同一页，不引路由库、状态库或其他依赖；旧模型/函数/校验器不改，只追加请求、响应协议。
- POST 入参 temp_c/occasion、可选 formality_target/excluded；默认正式度从 cases.json 的 filter_spec 读取。内部固定 `filter_candidates → generate_outfits → compose_outfits → client.chat`，其中 generate_outfits 是 T8 的最外层捕获，没有 mock 分支或模型名硬编码。响应必有 session_id/sets/degraded/degrade_reason/prompt_version/latency_ms。
- **本接口缺件按本轮批准的产品语义返回 HTTP 200**，不把衣柜不足当参数错；`shortage` 按缺失槽位索引（如 shortage.top），并带 shortage_hint，C01/C02 不调用模型。普通参数错仍为 400，旧衣柜 PATCH 的 422 与公共异常处理器保持不变；不修改案例数据或期望。
- 一次事务写 sessions、outfit_sets、outfit_items；正常输出的 reason/item_id/slot 标 model，规则降级标 derived。服务端计时从处理函数入口开始，覆盖读库、过滤、全部模型重试/等待、生成与结果事务提交，提交后回写同一个 latency_ms 到 sessions/响应；最后一次计时字段回写自身不计入。模型异常会写 failed session；读库本身失败时不能承诺留记录。
- 旧 sessions.fallback_type 枚举不扩表：timeout/parse_failed 分别保存 timeout/parse_fail；auth/rate_limit 保存 status=degraded、fallback_type=NULL，精确 degrade_reason 随本次响应返回，不冒充超时。不提供历史查询或持久化新归因列，后续需要历史精确归因时须按迁移规则另做。
- 前端从真实 POST 读取方案，逐套展示实际单品、颜色与理由；复用 getViewState 的 loading/empty/error，空态显示结构化缺件，错误态有重试。黄条位于页面顶部，全部归因共用样式，可关闭；以 session_id 作为组件 key，同轮表单重渲染不会重弹，新轮次重新显示。授权/限流/超时采用真实错误样本约定，解析失败采用 docs/04 F4 的「这次没生成好，已换成基础搭配。」首句，不提供尚未实现的换一套入口。
- 首次真实 curl 结果：HTTP 200，session_id=`S87674b064f9548f6b5ca54096833e9c2`，3 套、degraded=false、degrade_reason=null、prompt_version=outfit_compose.v1，**服务端总耗时 5583ms**，与 sessions 一致。浏览器另一次完整真实请求为 `S1ac6d9f990734177b6e677dbb0fb872c`、6141ms，同样正常出三套。仅为两次观测，不估算 P95。
- loading/出方案截图来自浏览器真实请求；黄条来自临时库中对客户端注入超时后产出的真实规则 API 响应，再仅在 CDP 浏览器层注入以验视觉与关闭行为。未给应用添加假数据开关，未制造真实模型超时。三张截图已查看，位置 `docs/reports/ui-t7/{01-loading,02-ready,03-degraded}.png`；375×812@2x，PNG 750×1624。

### 3.8 T8 · 降级与错误码
```bash
# 三种降级各跑一次，并各留一张截图
# 1) 衣柜只有夏装 + 8℃        → 200 + shortage_hint（T7 本轮批准语义）
# 2) 模型超时（离线注入）→ 200 + degraded=true + 顶部黄条 + 规则模板；公共超时异常处理器仍支持 504
# 3) 模型返回非 JSON            → degraded=true，黄条文案一致
```
判据：三条路径**都不允许白屏、都不允许暴露 traceback**，且黄条文案与 `docs/04` 一致。

T8-1 本轮实现（2026-11-13，人类批准后端八文件，T8-2 另做）：

- 范围为 `fallback.py`、`llm/errors.py`、`llm/client.py`、`compose.py`、`models.py`、`main.py`、`test_fallback.py`、`test_errors.py`。无 web、outfits 路由、初始化包、依赖、prompt 或迁移变更。两个测试文件的首批测试被并行 T6 提交 `41a5f82` 收录，本次继续补齐实现及回归，不改写该提交。
- **T7 必须调用 `generate_outfits`**：这是 compose.py 最外层的生产入口，默认真实 client.chat；T6 的 S3 函数 `compose_outfits` 保留带归因抛错契约，不添加测试/生产行为开关。最外层仅捕获已归因的 auth/rate_limit/timeout/parse；规则/过滤错误不伪装成降级。返回 `degraded=true` 和 `degrade_reason=auth/rate_limit/timeout/parse_failed`；C01/C02 shortage 保持直返，模型和模板均不调用。
- 真实 429/403 JSON 从 `docs/reports/api-error-samples.md` 直接读取。401/403 分类 auth、不重试，运维文案为「AI 服务未授权，请检查配置」，公共异常文案为「AI 服务暂不可用，请稍后再试」。日志分别记录 401/invalid_key 与 403/model_unpurchased，后者含真实 `AccessDenied.Unpurchased` 枚举。提供方自由文本不回显，provider_code 只记录已核实枚举，防止错误体反射敏感值。
- 429 默认调用可注入 `wait(retry_delay)`，retry_delay 默认 5 秒；同请求最多一次限流等待重试，计入共享三次调用预算。测试用立即返回的等待函数，不真睡 5 秒，也验证 retry_delay=0。首次 429 后成功的结果维持 `degraded=false`。超时不重试；非 JSON/schema 不符依旧带失败原因纠错一次，仍失败才由最外层降级。
- 规则模板分别按正式度总和降序、正式度总和升序（作为日常舒适策略的代理，并非体感舒适度模型）、厚薄总和降序选择不同组合，同分按 ID 稳定排序；理由固定模板引用实际单品属性，不调用模型。只有 1–2 种组合时按 D4 如实少出。每次模板生成后都用**原候选集**再次调用 validate；衣柜外 ID、重复品类/槽位、重复单品等仍被拒绝。规则结果是 derived，不能在未来落库时标成 model 来源。
- models 只新增错误/降级枚举、degrade_reason 和提供方错误协议类，旧字段默认值、校验器、derive_needs_confirm 未改。旧模型/函数 AST 一致性已检查，原有 110 项测试源文件与 T3 基线一致。每个实际模型尝试记 `event=model_call`；规则降级另记 `event=fallback`，不会被误算成一次 API 调用，累计耗时包含等待、重试和模板生成。
- main 注册公共 400/422/504/500 及模型异常处理器；普通参数校验为 400，保留 D8 衣柜 PATCH 的 422 约定；无合规方案的 422 可携带结构化 shortage 与 shortage_hint。这里只验证公共处理器，不声称已经存在 POST /api/outfits。
- 本轮未新增页面，也未做黄条、关闭按钮或三态截图；这些属于 T8-2。未使用真实模型，未重新验证 T6 实调用指标，T6 独立报告保持原状。

**T8 接入收尾（随 T7 完成）**：已接入真实方案页及 DegradeBanner；CDP 覆盖 timeout/rate_limit/auth/parse_failed 四种黄条、关闭按钮和同轮重渲染不复现，新轮次可再次显示，另覆盖错误重试恢复。timeout 黄条示例截图已归档 ui-t7/03-degraded.png，其余三种复用同一组件样式并实测关闭。T8-1 的离线抗体保持全绿，T8 标 ✅；本轮不扩展失败处理策略或重新跑 20 条评测。

### 3.9 T9 · reroll + 排除
人工：点"换一套" → 5 秒内出新方案，且**至少 2 套与上一轮不同**（B10 断言）。
判据：排除某件后，后续所有方案都不再出现该件（0 次）。

### 3.10 T10 · 评测跑批 v1
```bash
make eval    # 生成 docs/reports/eval_v1.md
```
判据：cases v2共29条，固定24行可跑明细（case_id / 通过 / 失败原因 / 归因 / 耗时）；A01–A05显式列「跳过：素材未备」，不计分母。汇总只报硬性通过数/24、各归因计数、识别与真实组合分别min–max+n，不报平均或预估。
- R01–R09用extract_record重放既有真实原文，标注录制日期；输入/期望摘要与录制源35e18aa核对，不用校正后的值重算指标。
- B01–B10固定filter_candidates→generate_outfits→真实client.chat，逐条保留原文/尝试/总耗时/降级标记/版本/时间戳。B05/B10只留一次基础生成，整例归「依赖未实现（T9）」，不混入四类模型侧归因；B类实际降级仍为硬性失败，不能以模板可用掩盖模型失败。
- C01/C02零模型调用；C03–C05在client传输层注入，记录为注入而非真实模型失败。C04直接注入超时异常，不实际等20s；黄条引用T7截图，未重做浏览器验收。
- 执行完整exit0，用例失败写报告；缺记录、用例与录制不一致、全部真实网络失败等跑批中断才非0。禁止覆盖既有原文或通过重跑美化v1；再次执行默认make eval会因证据已存在而明确中断，不发模型请求。原始首轮结果不改，未修改cases断言。

### 3.11 T11 · 评测口径收尾（✅）
最终状态说明：**识别稳定性 2/3，见 repeatability 报告**（R02/R03各3次的观测值，非总体识别准确率）。[重复实验](reports/t11-repeatability.md)显示R03单次转绿不足以证明已修复，本阶段不再出识别prompt v3，不改case断言。

收尾实际命令：
```bash
.venv/bin/python -m scripts.evaluate --repeats 3 --recognition-dir docs/reports/raw/recognition_v2 --output docs/reports/eval_v3.md --raw-dir docs/reports/raw
```
- `--repeats`默认1，官方基线保持单次布尔/24口径；N>1只对B类生效，逐例报告通过次数/N，分组汇总，不能按任一次或多数通过折回布尔，也不与v1/v2总通过数相减。
- 本轮N=3，B01–B10逐轮走完整filter→generate→真实client，每次生成独立遵守D7.1预算；30个场景32次客户端尝试，原文保存`raw/compose_v3/Bxx.rNN.json`，聚合保存`Bxx.json`。R仅重放既有v2录制，C规则/注入仍各跑一次，分别保存edges_v3/injections_v3。
- v3头部引用识别重复性结论，写明R类单次录制与报告入口；识别本轮零新调用，C04沿用T7黄条图、未重做浏览器验收。
- v1/v2证据、repeatability报告、prompts/cases等86个受保护文件哈希全部不变。任何部分v3原文已存在也拒绝新调用，不能通过改N覆盖或重新筛选结果。
- 识别sub枚举与同义词映射仅加P1入口注释，不改当前行为；人工可穿率尚未测量，不补造数字。按本轮人类裁定，T11以评测口径交付关闭，完整演示缺项进入T12说明。

第一轮v2的历史执行与边界：
```bash
.venv/bin/python -m scripts.record_recognition
.venv/bin/python -m scripts.evaluate --recognition-dir docs/reports/raw/recognition_v2 --output docs/reports/eval_v2.md --raw-dir docs/reports/raw
```
以上是本轮实际命令；证据已存在时拒绝覆盖，不得再次调用来改善数字。
- v1的29个受保护文件SHA256留于`reports/t11-v1-freeze.json`，含原prompt、原文、summary、CSV与eval_v1.md/json。B03只改fail_policy为BENCH，CHANGELOG追加更正说明；原v1通过数、归因文本与原文不回写。
- `item_extract.v2.md`与v1唯一差异是一句sub具体款型约束。识别九张真实重跑、并发3；走client.vision的20s超时/temperature=0/600 tokens、每张最多三次尝试，超时/未授权不重试，校验重试追加原因。既有文本chat与录制compare函数未改。
- `extract_record`按精确白名单v1/v2解析prompt_file，拒绝任意路径及符号链接，保留SHA核对。失败响应不因可解析就改判通过，协议失败/空原文保留在固定24条分母内；混版/缺记录中断。
- 新原文分别存`raw/recognition_v2/`（含summary_v2.json）、`compose_v2/`、`edges_v2/`、`injections_v2/`；B类仍完整过滤→生成→真实chat；C类注明注入，C04复用T7黄条图、未重做浏览器验收。A01–A05仍单列跳过。
- v2对照列R03、sub_in、总通过数及全部绿转红。v1识别录制器曾用120s且未显式指定温度，本轮按项目要求改20s与temperature=0，因此不能把差异全归于prompt，不能据此声称因果提升。
- 本轮只出prompt v2；若仍为上位词，记模型能力边界，不出v3调到通过。实际R03转绿，但R02回归，整体没有提升，未继续调参。
- v2后已补本轮B重复采样；人工可穿率盲评未做，未创建`user_review.md`。简历只使用任务板与实际报告可支持的观测值。

### 3.12 T12 · 文档收尾（🟡，演示缺项保留）
**2026-11-14作品材料补齐**：人类批准五文件范围：新增`docs/作品说明.md`，修改README、docs05、本任务板和CHANGELOG。按评审截图的五项标准补作品信息/链接/简介/设计/验收，注明本人负责内容与Codex辅助、开发中状态与公开链接缺失；引用既有真实照片和明确注入边界的T15图，不新增模型调用。更新当前回归283 pytest + 34 Vitest，删除简历中易被误读的“零抖动”结论，保留N=1与N=3分母及失败归因。仅核对链接/数字/旧证据哈希，不改功能、用例和冻结报告，未重做浏览器验收。文档补齐不代替完整录屏，T12仍🟡。

**T5-D2后更新**：上传建档现已真实接通，九张完整单张5411–8880ms（n=9），已同步README/docs05；完整60秒录屏仍缺T9，T12保持🟡。以下为T12当轮交付记录，未改历史评测报告。
本轮人类批准范围：`docs/05-简历文案.md`、`README.md`、`CHANGELOG.md`、`docs/tasks.md`。
- 已完成：简历A/B/口述版本与数字来源表，全部使用eval_v1/v2/v3和repeatability实际观测；去掉占位符、无依据的P95/人工可穿率/提升曲线/访谈分钟数，明确脚本识别与上传未接通的边界。
- 已完成：README顶部“30秒跑起来”，标明已有依赖与API配置前提；首次准备保留既有环境，介绍真实页面/API、分组评测口径和原文入口。
- 缺项：完整60秒演示需“真实上传建档→场景→三套→换一套→黄条”，受T5上传链路与T9未完成阻挡，本轮未录制、未创建demo文件；已批准先做文档，T12保持🟡。
- 未测：人工可穿率、HTTP端到端P95、完整首次建档时长；文档不给虚构数值。本轮不实现T5/T9、不新增模型请求或浏览器验收，不修改冻结报告。

---

## 四、现在不许做的事（提前做＝返工）

1. **不许动 T2 及以后**，直到 T1 的 `make test` / `make lint` 都 exit 0。
2. **不许写 `evaluate.py`**，直到 T6 完成（没有编排就没有可评的东西）。
3. **不许美化 UI**，T7 之前页面只要能看见字。
4. **不许把简历数字写死**，T11 之前 `docs/05` 里的 `【】` 全部保留占位。
5. **不许新增依赖**，需要就先在 `docs/backlog.md` 记一行并问我。

---

## 五、实测证据（每个任务完成后回填，一行一条）

| 任务 | 日期 | 实测证据（命令 + 关键输出） |
|---|---|---|
| T17主页入口修复 | 2026-11-20 | 旧根README按钮地址与上轮临时地址均匿名502/no tunnel；新通道首页/health200，仓库private=false。409 pytest+76 Vitest、lint通过；只更新根README入口及项目3份同步文档，发布后回读检查。见reports/t17-profile-entry-fix.md。 |
| T17同步T22 | 2026-11-20 | 509项快照、70项新增/更新（44文本+26图），远端64c1135d80166be8eab1d5d0dbbc013cd15a568c已回读；missing/mismatch/extra/outsideChanged均0。409 pytest+76 Vitest、lint通过；简历材料和配置密钥均未上传。后台临时HTTPS首页/health/最新App资源200，带设备头200/无设备头400，T22积分只读200；无新增模型调用，见reports/t17-sync-t22.md。 |
| T22最终 | 2026-11-20 | 409 passed in 5.98s、76 Vitest、lint exit0、build469ms；26张375×812均scrollWidth375/Runtime0。真实双设备积分10重复不增、收藏1、收到3互动+1关注、OOTD照片/方案引用持久化、异设备404、反馈保存；StrictMode浏览器选图保存成功。审查5项均修复，慢分页串栏3→0、设置浏览器返回正确、历史只读task快照。134冻结项不变、旧test_db断言不变；清空A后B保留、当日积分0不补领；无真实试穿、部署或GitHub同步，见reports/t22-personal-center.md。 |
| T22-F | 2026-11-20 | T22-F: 408 passed in 4.24s; Vitest 73 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22-E | 2026-11-20 | T22-E: 408 passed in 4.58s; Vitest 70 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22-D | 2026-11-20 | T22-D: 408 passed in 5.48s; Vitest 70 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22-C | 2026-11-20 | T22-C: 408 passed in 4.82s; Vitest 65 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22-B | 2026-11-20 | T22-B: 404 passed in 4.19s; Vitest 65 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22-A | 2026-11-20 | T22-A: 398 passed in 3.95s; Vitest 65 passed; make lint exit0. 新增测试先RED后GREEN；产品整体验收仍待完成。 |
| T22设计 | 2026-11-20 | 完整设计与独立builder check/复审完成，补删除重放拒绝、历史指定task_id、清空文件补偿及持久化恢复判据。git diff --check exit0；脚本核对A8/B7/C7/D8/E8/F8、only documentation changed、frozen=134; mismatches=[]。未修改产品代码/AGENTS，未运行功能test/lint或页面验收，设计/范围待批准。 |
| T17发布清理 | 2026-11-20 | 远端提交7dc181567d02ee94349d99e0e10728c2db3e0366已回读；递归tree确认两份专用文档不存在，456项项目文件、其他文件SHA不变。local originals=2 preserved; tracked=0; ignored=2; README links=0；技术截图poll-resumed不被误忽略。make test→394 passed in 4.08s + Tests 65 passed (65)；make lint→All checks passed!、tsc exit0；134冻结项mismatches=[]。本地原稿不上传，历史不改写，详见reports/t17-career-exclusion.md。 |
| T17同步T21 | 2026-11-19 | 本地3d742e7的457项快照同步公开AI衣橱/，58项新增/更新（35文本+23离线截图）；missing/mismatch/extra/outsideChanged均0，快照commitf1137c852f6a999201c7eb8dc0bf3f845744b471已回读。394 pytest+65 Vitest、lint exit0；凭据模式/运行路径命中0、134冻结项不变；另补同步记录，真实试穿未做，见reports/t17-sync-t21.md。 |
| T21离线收尾 | 2026-11-19 | 394 pytest+65 Vitest、lint exit0、build383ms；独立审查两项修复先RED后GREEN：丢回包新尝试同票重试生成2→2，查询错误后恢复轮询。23张CDP375×812均scrollWidth375、Runtime0；双设备私有job/结果404、A清空B保留、A2/B1匿名额度保留，ObjectURL9/9与7/7释放。134冻结项不变；只有隔离供应商注入3次，真实生成0次，不用截图冒充真人效果。T21保持🟡，见reports/t21-tryon-experience.md。 |
| T21-C实现 | 2026-11-19 | C8文件首页体验目录/详情/人物选择与处理说明/真实任务状态/结果切换/删除，首页上传入口移除、衣橱上传保留；7新增Vitest先缺模块RED后GREEN。392 pytest+64 Vitest、lint/build467ms通过；独立审查与375px待验。未发真实试穿调用。 |
| T21-B | 2026-11-19 | B8文件完成真实默认FASHN REST、体验目录与私有job API、结果存本地、清空接线；新增13后端用例，392 pytest+57 Vitest、lint全绿。缺key/未确认不创建，提交未知不重发，状态节流/30次预算、坏结果拒绝、清空在途提交/查询均无照片复活；全部供应商响应为离线测试注入，无实际生成。 |
| T21-A | 2026-11-19 | A7文件完成：素材有权导入dry-run/幂等、008纯创建迁移、独立匿名试穿额度账本、15分钟不过午夜ticket、原子任务保留与删除后410；新增6测试，379 pytest+57 Vitest、lint及脚本ruff通过。旧无列名INSERT导致采用独立额度表，旧断言未改；本地开发重载的早期008已备份补齐，旧业务计数不变、早期多余列保留。无真实调用。 |
| T21设计 | 2026-11-19 | 仅调研/设计文档：用户无平台商品资源，已选择体验素材+真实试穿路线；核对FASHN官方REST/计费单位/数据保留，未调用付费API。独立审查补删除后去重账本/短期ticket/午夜拒重，A7/B8/C8待批准。git diff --check通过；未运行功能测试、不宣称功能完成。 |
| T17同步T20 | 2026-11-19 | 本地eff55df的413项快照同步至公开AI衣橱/，70项新增/更新（36文本+34截图）；候选tree核验missing/mismatch/extra/outsideChanged均0，快照commit9daabff8e313de8220ad947c37c51ca96fcf1685已回读。373 pytest+57 Vitest、lint exit0；凭据模式命中0、运行路径0、134冻结项不变；另补同步记录，见reports/t17-sync-t20.md。 |
| T20收尾 | 2026-11-19 | `373 passed in 5.09s`+`Tests 57 passed (57)`、lint exit0、build426ms。真实临时API双设备四类发布/关注/赞/评论/投票，回包丢失重试3→3帖；A清空14件/2照片及社区、B1帖保留，匿名额度1保留。34张CDP375×812均scrollWidth375、Runtime0，ObjectURL A43/43 B50/50释放。审查修复图片结构/路径/history及嵌套WebP，回归先RED后GREEN；134冻结项不变，无LLM/天气调用。见reports/t20-community.md。 |
| T20-E实现 | 2026-11-18 | 7代码文件，帖子详情/真实互动/评论/四类发布及照片预览、失败草稿保留、设备切换阻止；新增1 Vitest先RED后GREEN，全量367 pytest+57 Vitest、lint/build364ms通过。独立审查与375px双设备验收待做。 |
| T20-D | 2026-11-18 | 8代码文件；6新增Vitest先缺模块RED后GREEN，367 pytest+56 Vitest、lint/build350ms通过。四栏目真实列表/公开照片/赞数与空错载入、设备头API及ObjectURL释放、底栏社区与衣橱子导航完成，详情发布待E。 |
| T20-C | 2026-11-18 | 3代码文件，3互动集成测试先404 RED后GREEN；367 pytest+50 Vitest、lint全绿。双设备关注/赞/评论、唯一并发投票、选项归属与清空后计数均真实SQLite验证。 |
| T20-B | 2026-11-18 | 6代码文件，跨设备公开读取/私人隔离/发布防重/四类型校验/分页/副本/路径防越界/撤回失败重试/清空配额保留7测试通过；364 pytest+50 Vitest、lint通过。发布接口最初404 RED，未使用模型或真实数据。 |
| T20-A | 2026-11-18 | 4代码文件，八张社区表及来源协议；新迁移/唯一/FK测试先缺协议RED后GREEN，357 pytest+50 Vitest、lint全绿。旧test_db仅新增精确表/字段检查，旧断言保留。 |
| T20设计 | 2026-11-18 | 人类已选择真实跨设备社区并批准AGENTS例外，单独提交4adaec8；设计独立只读审查无重大未决，A4/B6/C3/D8/E≤7范围待人类确认。私人衣橱保持owner隔离，只有显式发布副本公开；本轮未写产品代码、未调用模型或联网、未访问真实data；git diff --check通过。 |
| T17同步T19 | 2026-11-18 | 本地f9070c8的358项文件快照同步至公开AI衣橱/，59项新增/更新（32文本+27截图）。候选tree校验missing/mismatch/extra/outsideChanged均0，快照commit6874d2921aee6e33bf397e1b3cfa34cedefe72ec；正常前进、expected_sha校验，无强推。`355 passed in 3.10s`+`Tests 50 passed (50)`，make lint exit0；凭据模式命中0，无运行数据路径，134冻结项不变。另补同步记录，详见reports/t17-sync-t19.md。 |
| T19收尾 | 2026-11-18 | `355 passed in 3.54s`+`Tests 50 passed (50)`，make lint exit0、build425ms。真实GET cities200/3项3845ms（首次504/8043ms保留），forecast200/7天1577ms；浏览器真实搜索选城→预报→18°C带入通过。27张CDP375×812，scrollWidth375、Runtime0；上传失败File保留1、2次重试draft_id相同，黄条关闭有效。审查3项先RED后GREEN；134冻结项不变，无LLM调用。详见reports/t19-home-weather.md。 |
| T19-C实现 | 2026-11-18 | ≤6代码文件，354 pytest+50 Vitest及lint通过，build346ms；档案分区摘要/编辑、衣橱横分类/三列网格、天气预填与上传跳转接线完成。375px与独立审查待验，真实天气暂因TLS未通过。 |
| T19-B | 2026-11-18 | 8代码文件；天气API6测试先RED后GREEN，全量354 pytest+50 Vitest、lint通过，build335ms。粉色首页/真实衣物、天气搜索与7天卡、四入口底栏完成；C段继续详情/预填接线，375px待最终验收。 |
| T19-A | 2026-11-18 | 6代码文件，22天气测试先因模块缺失RED；实现后`354 passed in 3.23s`+`Tests 44 passed (44)`，make lint exit0。城市搜索200、预报TLS失败，真实天气未宣称通过；固定供应商域名、不转发设备资料、非法/过期/不完整响应拒绝。 |
| T17同步T18 | 2026-11-18 | 本地c6ffb75的312项文件快照同步至公开主页仓库AI衣橱/，新增/更新50项、额外远端文件0；候选tree逐项SHA/mode核对missing=0、mismatch=0、outsideChanged=0，main已回读至d7d88aebb6f0bbadcd28107f4dea4a6051bd7df0。另补同步记录文档。`make test`→`332 passed in 3.02s`+`Tests 44 passed (44)`；`make lint`→`All checks passed!`、tsc exit0。凭据模式命中0，无.env/data/依赖路径，134冻结项不变，无模型调用或部署。详见reports/t17-sync-t18.md。 |
| T18最终验收 | 2026-11-18 | `zsh -ilc 'make test && make lint'`→`332 passed in 3.07s`+`Tests 44 passed (44)`，ruff/tsc exit0；build392ms。CDP11张375×812截图scrollWidth均375、Runtime异常0；临时库真实GET/PATCH覆盖资料保存刷新、五型选择、分类空态/保存失败保留/成功迁移和设备切换保护。另浏览器回归自定义名称保留手选outer：先丢失为null RED，修复后PASS。只读审查4项已修复，最终修复7代码文件，134冻结项SHA256不变；无新增模型调用，不发布。详情reports/t18-profile-categories.md。 |
| T18-E代码 | 2026-11-18 | 329 pytest+42 Vitest及lint通过，build335ms；新增分类映射/计数/固定类别/手工命名3测试和API移动/失败保留1测试。5前端文件，375px截图及最终审查待验，T18保持🟡。 |
| T18-D2 | 2026-11-18 | 分类后端8文件完成，新增9测试，329 pytest+38 Vitest及lint通过。006只增列并幂等回填；外套归上装、半裙归裙装且底层槽位保留。新增v3类别schema由models生成，包包/首饰/套装/unknown入库待确认，未分类需手工归类，非衣物仍422；收纳类不推荐，来源可追溯。生产上传版本断言随功能由v2更新为v3，旧v1/v2与案例不改。 |
| T18-D1 | 2026-11-18 | 人类批准D1/D2拆分。新增迁移回放回归先因重复加列失败，再暴露人工分类被覆盖；结构核对与只回填NULL修复后329 pytest+38 Vitest、lint全绿。test_db旧库夹具仅移除001不存在的新列，并增加迁移后分类断言；旧表/owner/外键/数量断言保留。D1代码仅db.py、test_db.py、test_owner_isolation.py。 |
| T18-C | 2026-11-18 | 3条资料接入/降级版本测试先RED，完成后319 pytest+38 Vitest、lint全绿。仅本设备资料进入S3，候选ID不变，无资料仍v1；有资料v2响应/session一致。编排v2仅在旧v1基础新增身材用途/禁用合身推断说明，schema仍单一来源。 |
| T18-B | 2026-11-18 | 新增profileApi4测试先因模块缺失RED，完成后316 pytest+38 Vitest全绿，lint通过；五种SVG轮廓和原文描述、正数/空值、小数、GET/PATCH设备头与保存失败均覆盖。资料页及导航完成，375px截图待E最终验收。 |
| T18-A | 2026-11-18 | 新增14条临时库资料API测试先13失败（接口404），实现后全量316 pytest+34 Vitest通过；make lint通过。GET/PATCH保存/刷新、小数、五型、设备隔离和清空均验证；迁移重复执行成功。旧test_db增加新表与完整字段检查，A共7代码文件。 |
| T17公开源码 | 2026-11-16 | 主分支286文件（含47张测试素材/验收截图）共7719302字节，公开至主页仓库AI衣橱/；凭据扫描未发现真实密钥，.env/data/.venv/node_modules未上传。远端tree与本地Git逐文件比对：missing=0、hash_or_mode_mismatch=0、unexpected_files=0。保留原主页README并加源码入口，非强制更新远端main；公开网页与后续文件回读另行核验。`make test`→`302 passed in 2.70s` + `Tests 34 passed (34)`；`make lint`→`All checks passed!`、tsc exit0。发布当前主分支文件快照，不含未合入T14或本地Git历史，不改功能/prompt/cases/冻结证据、未新增模型调用。 |
| T16轮换与后台补修 | 2026-11-16 | 旧URL实际502/no tunnel、本地health200，通道日志已有新域名但脚本读取首条；旧主进程消失而子进程仍存活，退出原因未确定。追加5条回归：最新域名、先验证再更新两分支、父进程组退出后台存活、相对解释器身份识别。`make test`→`302 passed in 2.69s` + `Tests 34 passed (34)`，lint/脚本ruff通过；后台启动返回后主进程PPID=1且自有进程组，公网health/root均200，status可查，模型日志仍4条。见reports/t16-rotation.md，未重新调用模型或重做UI。 |
| T16保活补验 | 2026-11-16 | 发布前发现SSH闲置超时与公网短暂502；新增保活和软失败2条先RED后GREEN回归，现14 share tests；全量`297 passed in 2.80s` + `Tests 34 passed (34)`，lint/脚本ruff通过。make share实际重启后公网约1分钟5次health均200，进程一直运行，模型日志仍4条；原文见reports/t16-keepalive.json。旧域名失效及网络波动记录保留，临时地址不承诺长期有效。 |
| T16 | 2026-11-16 | 新增12 share tests→`12 passed in 0.40s`；`make test`→`295 passed in 2.47s` + `Tests 34 passed (34)`；`make lint`/`ruff check scripts/share.py`通过。公网3张真实照片POST201并确认，真实POST outfits200/1套/degraded=false/5026ms；A3件B0件、跨owner照片404。Cloudflare7844失败后系统SSH备用通道成功；实际Ctrl-C释放18080并移除状态，默认make share重启成功、build355ms，最终health200/root200/新设备GET200空/缺头400。免费带宽导致方案3图文字降级，不伪报图全正常；计时驱动边界与初始检查失败留报告。六代码文件，134冻结项未改；T14/T9不推进。 |
| T12作品材料 | 2026-11-14 | `zsh -ilc 'make test'`→`283 passed in 2.12s` + `Tests 34 passed (34)`；`zsh -ilc 'make lint'`→`All checks passed!`、tsc exit0。作品说明五个编号章节齐全；README/docs05/作品说明共61个本地引用均可解析；脚本核对原件v1/v2各20/24、B21/30、90套均在衣柜内，冻结134项SHA256不变。复看T13衣柜图与既有T15预览图，独立只读审查无阻断；保留真实模型/录制/注入边界。仅五文档，无新模型调用或UI改动；完整视频、公开URL、T9仍缺项，T12保持🟡。 |
| T15 | 2026-11-14 | `make test`→`283 passed in 2.55s` + `Tests 34 passed (34)`；`make lint`→`All checks passed!`、tsc exit0；前端build367ms。后端新增4条先405 RED再全绿；前端新增5条先RED再全绿。CDP七图均375×812、scrollWidth375、brokenImages0、Runtime0；失败23件保留，真实临时库删除23→22，再删404，引用0/照片已删/FK0。ObjectURL创建27/释放27/残留0；client层编排离线注入及图片/删除故障注入明确标注，不算真实模型验收。D10-c先行独立提交86a4e07，冻结134项不变；七代码文件。 |
| T13-C最终 | 2026-11-14 | `make test`→`279 passed` + Vitest `Tests 29 passed (29)`；`make lint`→ruff/tsc exit0；build308ms。CDP五图375×812、scrollWidth375、Runtime0；卡片无ID/编辑有ID、断网保留input/File/同draft。QA状态复位验未改字段保存仅POST confirm且category仍model；业务响应no-store/Vary。旧134文件hash不变，C仅5代码文件；B新增fixture类型错误已修并纠正当轮汇报。历史probe不计验收，未部署/T14/T9。 |
| T13-B审查修复 | 2026-11-14 | 未改字段保存的RED测试复现伪造category PATCH后，改为api显式confirm；空PATCH后端仍422。279 pytest+28 Vitest通过；当轮lint因fixture TS2322未通过，已在C补类型注解并重跑279+29/lint全绿。category模型来源不伪标user；仅3代码文件。 |
| T13-A审查修复 | 2026-11-14 | 审查复现设备UUID编码进ID/缺缓存头/跨午夜等待记旧日；4条新增RED抗体后转绿。全量279 pytest+27 Vitest、lint通过；004幂等迁移owned23条opaque ID，总47→47、legacy24逐字段不变、FK0违规。业务响应no-store/Vary，日期改在写锁内采样；新上传随机ID、seed稳定盐映射。修改6代码文件，C暂存待恢复。 |
| T13-B九张真实 | 2026-11-14 | 真浏览器→原omni模型/v2→入库，needs_confirm初始9/9，R01界面PATCH、其余8张点这是对的，刷新/SQLite均false9/9、confidence仍model。额度9、实际模型尝试12且每张≤3。首张截图超时/页面刷新，模型已成功写库，相同draft缓存重读0新增识别；首调总耗时缺失如实保留。R02仍top/0.95但正确进入待确认，不冒充准确率改善。274 pytest+27 Vitest与lint/build通过；C尚未执行。 |
| T13-B后端 | 2026-11-14 | D10-b先单独提交7099171，再实现统一派生规则与owner隔离确认路由；274 pytest+25 Vitest、lint通过。0.95高置信度错类目待确认、显式确认不改属性/来源、跨设备404与额外body422、迁移只回填未编辑上传均通过；真实legacy旧上传10/10变待确认，基准14不变。九张真实重跑待前端接入。 |
| T13-A3 | 2026-11-14 | 全量263 pytest + 25 Vitest、lint/build通过；设备UUID仅deviceId.ts持久化，组件无localStorage/fetch；照片带设备头取blob。真实CDP两设备A显式seed14/B0，刷新UUID不变、初始均不见legacy；375×812无横溢、Runtime0。A隔离已闭环，进入B前先单独提交D10-b；当前未改变确认规则。 |
| T13-A2 | 2026-11-13 | 全量263 pytest + 15 Vitest与lint通过；真实两个UUID上传201/201，B初始[]、跨照片/PATCH404；A实际生成3套后四表15/1/3/12清为0/0/0/0，A照片删除、B1件保留，计数识别1/编排1保留；legacy24/2/6/18不变。离线API配额20→第21次429、30→第31次429，并发24仅20接受；午夜/重启/失败扣次/缓存免费/清空互斥已验。匿名配额无UUID，盐0600，隐私文案已补。 |
| T13-A1 | 2026-11-13 | 全量250 pytest + 15 Vitest、make lint通过；真实库备份后迁移两次，四表行数24/2/6/18均保留、owner全legacy、原属性不变。claim_legacy默认dry-run打印24/2/6/18，未实际认领。134冻结文件不变；回滚命令见t13-data-isolation报告。 |
| T5-D2 九张上传/幂等/375px | 2026-11-13 | CDP真实浏览器选择8张+拖拽1张→真实omni模型→入库→照片卡片，9/9成功，R01–R09完整ms依次6278/6635/6314/7015/6632/5411/6248/8880/6431，范围5411–8880(n=9)；corrections 0/9张、0条，sources审计逐条一致。直查`SQLite count: 15 -> 24; cached retries: 24 -> 24`、`model attempts: 9 -> 9; one row per draft: 9/9; sources/photo SHA256 match: 9/9`；真实断网两次保留File/input/占位/同draft。截图ui-t5d、原文raw/upload，均375×812且scrollWidth375；empty/loading仅GET注入另标明。 |
| T5-D2 回归与边界 | 2026-11-13 | `zsh -ilc 'make test && make lint && cd web && npm run build'`→`244 passed in 1.27s`、Vitest `Tests 15 passed (15)`、`All checks passed!`、tsc exit0、`built in 290ms`。新增6条前端测试，旧GET晚成功合并/晚失败不遮新卡，原测试未删改；D2仅3代码文件，无新依赖/组件库，Wardrobe无直接fetch。`134 frozen files unchanged`。首次10张录入、真实非衣物、手动表单、T9和完整录屏未做。 |
| T5-D1 真实上传与SQLite门闸 | 2026-11-13 | 真TestClient multipart上传cloth01.jpg（非模型注入）→`D1 real gate HTTP 201 client_total_ms= 5708`；直连SQLite输出`SQLite count: 14 -> 15 ; retry count: 15`、`sources confidence= model warmth= model ; corrections= {'source': 'derived', 'entries': []}`；API及库内sources逐项一致。成功重传200/reused，原文与SQL快照见raw/upload/d1-gate.json；1次真实模型尝试，缓存重试0新调用。此为额外门闸，不计正式九张浏览器样本。 |
| T5-D1 单测/依赖与范围 | 2026-11-13 | `make test`→`244 passed in 1.35s` + Vitest `Tests 9 passed (9)`，`make lint`→`All checks passed!` + tsc，均exit0；相关两文件85项通过。覆盖校正来源/落库、低置信度与编辑、幂等与同ID换图409、超时后显式重试、五类错误、非衣物、MIME及元数据防误标；额外临时SQLite插入故障确认`rows=0, photos=0`。只新增python-multipart==0.0.33，既有已装/锁定版本不变。保护输出`134 frozen files unchanged; derive_needs_confirm/text chat and all old tests unchanged`；代码配置恰好8文件，未进入web，未改prompt/cases或数据库列。 |
| T12 文档与范围核对 | 2026-11-13 | 本轮只改README、docs/05-简历文案.md、CHANGELOG、tasks。文档检查实际输出`T12 docs: 25 local links valid; numeric claims match eval_v3; no placeholders or template metrics`、`frozen evidence/prompts/cases: 86/86 unchanged; v3 and runtime code unchanged`；简历A/B/口述及数字表引用单次20/24、B重复21/30、R单次8/9、C5/5与识别重复观测各2/3，各自分母和来源分开。README顶部启动命令与当前Makefile/CLI契约核对；双服务启动和375px截图沿用T1/T3/T7既有证据，本轮未重新启动服务、浏览器验收或录屏。 |
| T12 回归与未做项 | 2026-11-13 | `make test` → `230 passed in 1.06s` + Vitest `Tests 9 passed (9)`，exit0；`make lint` → `All checks passed!` + `cd web && npx tsc --noEmit`，exit0。T11已✅，T12文档完成但整体🟡：上传建档未接通、T9未实现，完整60秒演示未录制；人工可穿率、HTTP端到端P95、完整建档时长无实测，不填虚构数值。本轮无额外API调用、依赖变更或生产代码改动。 |
| T11 收尾N=3真实采样 | 2026-11-13 | `.venv/bin/python -m scripts.evaluate --repeats 3 --recognition-dir docs/reports/raw/recognition_v2 --output docs/reports/eval_v3.md --raw-dir docs/reports/raw` → `报告：docs/reports/eval_v3.md；B累计通过 21/30；R单次录制 8/9；C单次规则/注入 5/5`，exit0。B01/B02/B04/B06/B07/B08/B09各3/3，B03/B05/B10各0/3；失败样本归因BENCH=3、T9依赖=6，R单次IN=1；最终COMPOSE/PARSE/FILTER=0。2026-11-13 16:29:33–16:33:33(+08:00)，B耗时4178–14054ms,n=30；32次客户端尝试，B02.r01网络重试、B02.r03套数校验重生成，其余各首调成功；最终degraded=0/30，90套输出衣柜外ID=0。官方v1/v2各20/24保持冻结，不把重复分母混成单次通过数。 |
| T11 收尾回归与证据 | 2026-11-13 | `make test` → `230 passed in 1.05s` + Vitest `Tests 9 passed (9)`，exit0；`make lint` → `All checks passed!` + `cd web && npx tsc --noEmit`，exit0；额外`ruff check scripts/evaluate.py`通过。评测单测24项；新8项覆盖N3只乘B/30次调用、R仅9次读取无视觉调用、C不乘N、2/3聚合不折布尔、默认N1、非法N、v3目录与部分旧采样预调阻断。实际保护输出`frozen evidence/prompts/cases: 86/86 unchanged; extract AST unchanged (comment only)`、`manifest/raw consistency and secret/base64 scan: clean`。注释指向repeatability的P1枚举入口；未改prompt/cases、未动前端或数据库。 |
| T11 第一轮真实识别 | 2026-11-13 | `.venv/bin/python -m scripts.record_recognition` → `真实识别：8/9；sub_in=8/9；耗时 5194–9307ms, n=9；墙钟22855ms`，exit0。新录制qwen3.8-omni-flash，HTTP200=9/9、解析9/9、围栏8/9；并发3，9个场景共10次客户端尝试（R06首次网络失败后成功）。R03实际sub=`阔腿束腰休闲裤`转绿；R02实际category=`top`、sub=`拉链短款长袖T恤`，原期望outer及防晒服/夹克/风衣均不命中，唯一识别绿转红。原文与summary_v2.json完整留于raw/recognition_v2，未重放v1冒充新调用。 |
| T11 第一轮组合与对照 | 2026-11-13 | `.venv/bin/python -m scripts.evaluate --recognition-dir docs/reports/raw/recognition_v2 --output docs/reports/eval_v2.md --raw-dir docs/reports/raw` → `报告：docs/reports/eval_v2.md；硬性通过数 20 / 24`，exit0。完整过滤→生成→真实chat，qwen3.8-flash，5061–10855ms,n=10，全部degraded=false；10场景共11次客户端尝试（B02首次只出2套，带COMPOSE校验原因重生成成功）。v1→v2：R03失败→通过、sub_in 8/9→8/9、总通过20/24→20/24，绿转红仅R02。本轮IN=1、BENCH=1、FILTER/COMPOSE/PARSE=0、T9依赖=2；B03外套仍有W03，按授权只改归因、不改expect。5条A仍显式跳过，C为规则/注入，T7黄条图未重拍。 |
| T11 离线回归与冻结 | 2026-11-13 | `make test` → `222 passed in 0.96s` + Vitest `Tests 9 passed (9)`，exit0；`make lint` → `All checks passed!` + `cd web && npx tsc --noEmit`，exit0；额外`ruff check scripts/evaluate.py scripts/record_recognition.py`通过。20项新增测试覆盖v2仅一行prompt差异、白名单/路径/符号链接、哈希不匹配、视觉重试追加校验原因/三次上限/超时与auth不重试/429可注入等待、并发3与有序结果、禁止覆盖、空原文和可解析失败响应仍保留24分母、CLI参数与绿转红对照。保护检查原输出`v1 frozen SHA256: 29/29 unchanged`、`existing chat, compare, and all pre-existing tests: unchanged`、`v2 report/manifest/raw evidence: consistent; 24 rows + 5 explicit skips`、`code/config/data files: 8`；新证据检查`v2 evidence secret/base64 scan: clean`。 |
| T10 首轮真实跑批 | 2026-11-13 | `make eval` → `报告：/Users/yuanying/Desktop/算法衣橱/docs/reports/eval_v1.md；硬性通过数 20 / 24`，exit0。DASHSCOPE_MODEL=qwen3.8-flash、prompt_version=outfit_compose.v1。报告含24行明细与5条显式跳过；识别原录制5880–24888ms,n=9，真实组合5664–11923ms,n=10。10份B原文共11次尝试，全部degraded=false；失败为R03(IN，长裤未命中sub_in)、B03(COMPOSE，外套实际W02/W03/W10，允许W02/W10)、B05/B10(依赖未实现T9)，FILTER=0、PARSE=0。原文与逐条checks见`reports/raw/compose/`及`reports/eval_v1.json`，未调标准或重跑美化。 |
| T10 边界与客户端注入 | 2026-11-13 | 原始记录检查输出：`C01 attempts=0 passed=True degraded=False`、`C02 attempts=0 passed=True degraded=False`、`C03 attempts=2 passed=True degraded=False`、`C04 attempts=1 passed=True degraded=True`、`C05 attempts=2 passed=True degraded=False`。C03首次围栏触发PARSE反馈再成功；C05首次同套两件真实上装触发COMPOSE反馈再成功；C04直接注入超时异常，不以4ms注入耗时声称真实超时性能，引用已验收`ui-t7/03-degraded.png`，未重做浏览器验收。 |
| T10 测试与证据保护 | 2026-11-13 | `make test` → `202 passed in 0.87s` + Vitest `Tests 9 passed (9)`，exit0；`make lint` → `All checks passed!` + `cd web && npx tsc --noEmit`，exit0；额外`ruff check scripts/evaluate.py`通过。13项新增测试含完整filter→generate→chat顺序、固定24+5、R03失败不改、录制期望漂移预调中断、B类解析失败不能以规则降级冒充通过、缺记录/全网络失败非0、普通用例失败exit0、禁止覆盖原证据。证据检查真实输出`evidence_secret_scan: clean`、`runnable=24 skipped=5 raw_compose=10`、`report: 24 detail rows, 5 explicit skips, no averages`；`git diff bd6afe0 -- cases prompts app/services app/models.py app/llm web`与`git diff --check`均无输出，原测试未改。 |
| T5 离线真实原文与指标 | 2026-11-13 | `.venv/bin/python -m scripts.batch_extract` → `用例 9 \| HTTP 200 9/9 \| 解析 9/9 \| 用例通过 8/9`；`原始围栏 6/9 (67%) \| 单张平均 16258ms \| 原并发3墙钟 56939ms`；category/color_in/confidence_gte/formality_range 各9/9，pattern2/2，sub_in8/9。直接读取 summary.json，exit1保留R03失败；不是本轮新调用或重放墙钟耗时。CSV已写，逐条原耗时范围5880–24888ms。 |
| T5 测试与来源保护 | 2026-11-13 | 新测试 `.venv/bin/python -m pytest -q app/tests/test_extract.py` 共22项通过；`make test` → `189 passed in 0.73s` + Vitest `Tests 9 passed (9)`，exit0；`make lint` → `All checks passed!` + `cd web && npx tsc --noEmit`，exit0；额外 `ruff check scripts/batch_extract.py` 同样通过。保护项真实输出 `prompts/cases/models/client/web unchanged; all 167 pre-existing tests unchanged`；`prompt_sha256_prefix: 148a10064d22f145`。 |
| T7 首次真实端到端 | 2026-11-13 | `curl -sS -X POST http://localhost:8000/api/outfits -H 'content-type: application/json' -d '{"temp_c":18,"occasion":"commute"}'` → HTTP `200`，解析输出 `{"session_id":"S87674b064f9548f6b5ca54096833e9c2","latency_ms":5583,"degraded":false,"degrade_reason":null,"prompt_version":"outfit_compose.v1"}`、`sets: 3`；数据库输出 `{'latency_ms': 5583, 'status': 'ok'}`。当前模型配置读取结果 `configured text model: qwen3.8-flash`，client.py 未改。 |
| T7 缺件与持久化 | 2026-11-13 | 临时库只留 W04/W06/W09 三件，真实 TestClient POST C01 参数 → `C01 temporary wardrobe count=3: HTTP 200`，`shortage.top={"slot":"top","warmth_min":2,"formality_min":4}`，sets=[]、degraded=false；另含 outer 缺件，无真实模型调用。新测试 `.venv/bin/python -m pytest -q app/tests/test_outfits_api.py` → `15 passed in 0.25s`；验证三表关联、模型/规则来源、可选排除与正式度、失败 session，以及假等待 5s 回写总耗时 5000ms（没有真睡）。 |
| T7/T8 全量回归 | 2026-11-13 | `make test` → `165 passed in 0.54s` ＋ Vitest `Tests 9 passed (9)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0；`cd web && npm run build` → `34 modules transformed`、`built in 303ms`。AST/源检查输出 `models: existing classes/functions unchanged, protocol additions only`、`original 110 test sources and client.py unchanged`。 |
| T7/T8 375px 截图与黄条 | 2026-11-13 | CDP `Emulation.setDeviceMetricsOverride` width=375 height=812 deviceScaleFactor=2 mobile=true，`Page.captureScreenshot`；真实 loading、出三套、四类黄条、缺件 empty、error/retry 各状态均输出 `{"innerWidth":375,"scrollWidth":375,"height":812}`。关闭后每类均输出 `dismissed ...: same-round rerender remains closed`；错误重试输出 `error retry recovered to three basic outfits`。三张 PNG 已逐张查看，黄条完整可见，可关闭，无横向溢出。 |
| T8-1 分类与模板 | 2026-11-13 | `.venv/bin/python -m pytest -q app/tests/test_errors.py app/tests/test_fallback.py` → `40 passed in 0.18s`，exit 0。包含真实 429/403 夹具、401/403 无重试且日志区分、timeout 无重试、非 JSON/schema 一次纠错后降级、429 重试救回且不降级、混合三次预算、B01–B10 模板复验、候选外 ID/重复槽位品类/重复单品注入拒绝、C01/C02 零模型/零模板及公共错误码。 |
| T8-1 429 调用数抗体 | 2026-11-13 | `.venv/bin/python -m pytest -q -s app/tests/test_errors.py::test_429_twice_generates_fallback_with_exact_two_calls` → `429 assertion: model_calls=2, retries=1, wait_requests=[5], degraded=true, degrade_reason=rate_limit`、`1 passed in 0.15s`。wait_requests 是立即返回假等待收到的参数，不是真实睡眠。 |
| T8-1 原有测试与全量回归 | 2026-11-13 | 六个原测试文件单独执行 → `110 passed in 0.53s`；`make test` → `150 passed in 0.58s` ＋ Vitest `Tests 9 passed (9)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0。模型 AST 检查 → `models: all pre-existing class/function bodies unchanged; only additions`；测试源检查 → `original 110 tests: source unchanged against T3 baseline`。 |
| T8-1 零网络与范围 | 2026-11-13 | `grep -nE 'httpx\|requests' app/services/fallback.py` 无输出，exit 1（无匹配）；`git diff --check` 无输出，exit 0。HTTP 仅用离线 MockTransport，临时 .env/日志位于 tmp_path；未读取真实 key、未调用真实模型、未改 web。T8 保持 🟡 等 T8-2。 |
| T3 后端及前端回归 | 2026-11-13 | `.venv/bin/python -m pytest -q app/tests/test_wardrobe_api.py` → `32 passed in 0.31s`；`make test` → `110 passed in 0.46s` ＋ Vitest `Tests 9 passed (9)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0。新增 API 测试全部 tmp_path，含五字段来源/持久化、未知/只读字段拒绝与失败不部分写入、0.6/缺失值边界、低置信度死锁回归；前端新增 5 测覆盖 loading、empty、PATCH 本地更新及失败保留。 |
| T3 curl（重启后） | 2026-11-13 | §3.3 四条命令实际执行：GET 前 300 字符以 `[{"sources":{"sources":"derived","id":"derived","name":"model"` 开始，解析总计 12 件；PATCH W01 返回完整单品，摘录 `"sub":"白衬衫"`、`"confidence":null`、`"needs_confirm":false`、`"user_edited":true`，HTTP `200`；W99 → `{"detail":"这件单品不存在，请重新加载衣柜。"}404`；warmth=9 → `{"detail":"修改内容无效：只允许修改品类、子类、颜色、材质和图案；请检查字段、类型和品类枚举值，且至少修改一项。"}422`。 |
| T3 375px 三态与编辑 | 2026-11-13 | CDP 实际输出 loading/empty/error/ready-after-retry/editor/save-error-input-preserved/ready-after-refresh 均为 `{"innerWidth":375,"scrollWidth":375,"height":812}`；三张 PNG 已查看，empty 引导完整、error 重新加载按钮可见。浏览器表单字段输出 `["品类","子类","颜色（多色用逗号分开）","材质","图案"]`；注入 PATCH 503 后输入保留，解除注入后实际 PATCH `200`、顶部提示与卡片更新；刷新后仍为已保存值，最后通过 PATCH `200` 恢复 W01 的验收临时子类/颜色值（编辑来源保留 user）。 |
| T3 构建 | 2026-11-13 | `cd web && npm run build` → `31 modules transformed`、`built in 311ms`，exit 0；`git diff --check` 无输出，exit 0。未新增依赖，未调用模型，T6 真实调用仍待额度。 |
| T6 离线编排与校验 | 2026-11-12 | `.venv/bin/python -m pytest -q app/tests/test_compose.py app/tests/test_validate.py` → `32 passed in 0.10s`，exit 0；覆盖合法三套、重复上装、候选外 ID、套内重复、禁词、温度/连衣裙规则、非 JSON 两次失败 PARSE、校验反馈后成功、C01/C02 shortage 且调用数 0、prompt 动态 schema、诚实少出、无 key/超时/敏感响应不泄密、日志、共享三次预算、预算耗尽保留原归因及累计耗时。所有响应均离线注入。 |
| T6 全量回归 | 2026-11-12 | `make test` → pytest `78 passed in 0.39s` ＋ Vitest `Tests 4 passed (4)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0；`git diff --check` 无输出，exit 0。八个代码/配置文件，未改 cases、依赖、前端或数据库结构。 |
| T6 真实调用 | 2026-11-13 | 真实模型 `qwen3.8-flash` 跑 B01/B03/B05 三条：均产出 3 套、`degraded=false`、`prompt_version=outfit_compose.v1`，compose 耗时 6183/6652/6374ms（均值 6403ms，<12s 目标）。理由均引用真实属性，未触发禁词拦截。完整记录：`docs/reports/t6-real-call.md`。 |
| T4 测试与规则来源 | 2026-11-12 | `.venv/bin/python -m pytest -q app/tests/test_filter.py` → `25 passed in 0.04s`；包含 12 条源案例过滤断言及边界、显式/默认正式度、空 override、季节交集、dress 替代、计数纯计算和非法温度类型回归。`grep -nE "httpx\|requests\|urllib\|llm" app/services/filter.py` 无输出，exit 1（无匹配）。 |
| T4 全量回归 | 2026-11-12 | `make test` → pytest `46 passed in 0.33s` ＋ Vitest `Tests 4 passed (4)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0。未改原测试或案例期望，未新增依赖/初始化包文件。 |
| T4 组合基准与缺件 | 2026-11-12 | §3.4 的 12 行为实际终端输出；B02/B07=3、B05=12、B08=18、C01/C02=0，候选槽位件数均与人类参考一致。C01 缺 top（warmth_min=2、formality_min=4）；C02 缺 top/shoes/outer（warmth_min=3/2/2、formality_min 均为3），阈值来自规则/输入，不生成衣柜外单品。 |
| T2 首次 seed | 2026-11-12 | `make seed` → `衣柜初始化完成：本次新增 12 件，当前共 12 件。`；`sqlite3 data/app.db "select count(*) from wardrobe_items;"` → `12`；CLI SQLite 3.51.0、Python SQLite 3.53.1。 |
| T2 约束与分类 | 2026-11-12 | `sqlite3 data/app.db ".schema outfit_items" \| grep -i unique` → `UNIQUE (set_id, slot)`；`select category,count(*) from wardrobe_items group by category;` → `bottom\|4`、`outer\|3`、`shoes\|2`、`top\|3`。 |
| T2 幂等 | 2026-11-12 | `make seed && sqlite3 data/app.db "select count(*) from wardrobe_items;"` → `本次新增 0 件，当前共 12 件。`、`12`；临时库测试确认重复 seed 不覆盖已有用户修改。 |
| T2 全量与隔离 | 2026-11-12 | `make test` → pytest `21 passed in 0.57s`（含 17 项新 DB 测试）＋Vitest `Tests 4 passed (4)`，exit 0；`make lint` → `All checks passed!`＋`cd web && npx tsc --noEmit`，exit 0；完整测试退出后再查真实库 count → `12`，前后数据库文件 SHA-256 一致。案例与前端未修改，data/app.db、data/uploads/ 未纳入 Git。 |
| T1-A | 2026-11-12 | `pytest -q app/tests` → 4 passed；`ruff check app` → All checks passed；`curl /health` → 200 `{"status":"ok"}` |
| T1-B | 2026-11-12 | 历史记录：`npm run build` → 28 modules, built in 1.63s；`npm run typecheck` → exit 0；375×812 无横向滚动。原命令使用内置运行时，不作为人类终端可复现的最终验收；本轮重新验证见 T1-0。 |
| T1-0 | 2026-11-12 | 人类终端环境 `node -v` → `v22.23.5`、`npm -v` → `10.9.9`；仓库根目录 `make test` → `4 passed in 0.14s`（pytest）＋`Tests 4 passed (4)`（Vitest 5.1.0），exit 0；`make lint` → `All checks passed!`＋`cd web && npx tsc --noEmit`，exit 0；`cd web && npm run build` → `29 modules transformed`、`built in 323ms`，exit 0。 |
| T1-0 保护项 | 2026-11-12 | 安装前后审计输出：`Existing lock entries unchanged: 120`、`Existing installed versions unchanged: 49`、`main.tsx and tsconfig.json unchanged: yes`；Vite 仍为 7.3.8，Vitest 为 5.1.0，禁用新增包为 0。生产 App chunk 检查：`URLSearchParams: False`、`location.search: False`；隔离的前端失败注入：`make test` / `make lint` 均 `exit 2`，未吞掉失败。 |
| T1 收尾 a：首次启动 | 2026-11-12 | 人类终端环境 Node `v22.23.5` / npm `10.9.9`；根目录 `make dev` 同时启动双服务；`curl -s localhost:8000/health` → `{"status":"ok"}`；`curl -s -o /dev/null -w "%{http_code}" localhost:5173/` → `200`。 |
| T1 收尾 b：Ctrl-C 退出 | 2026-11-12 | 实际发送 Ctrl-C 后日志：`Application shutdown complete.`、`Stopping reloader process`；`lsof -ti :8000 -ti :5173` 无输出（exit 1 表示无匹配进程），两个端口均已释放。 |
| T1 收尾 c：立即重启 | 2026-11-12 | b 的端口检查之后立即再次执行 `make dev`，前端输出 `VITE v7.3.8 ready in 116 ms`，后端输出 `Application startup complete.`；相同两条 curl 再次分别返回 `{"status":"ok"}`、`200`。第二次 Ctrl-C 后相同 lsof 仍无输出。 |
| T1 代理与预览入口 | 2026-11-12 | `curl -s -i localhost:5173/api/health` → `HTTP/1.1 404 Not Found`、`server: uvicorn`、`{"detail":"请求的接口不存在。"}`，后端日志为 `GET /api/health`，证明代理保留 `/api` 前缀并到达后端；该后端路由尚未定义，未冒充 200。`curl -s -o /dev/null -w "%{http_code}" 'localhost:5173/?state=loading'` 与 `/?state=error` 均返回 `200`；仅证明入口可达，**三态截图待人类验收**。 |
| T1 收尾回归 | 2026-11-12 | 根目录 `make test` → pytest `4 passed in 0.16s` ＋ Vitest `Tests 4 passed (4)`，exit 0；`make lint` → `All checks passed!` ＋ `cd web && npx tsc --noEmit`，exit 0；`cd web && npm run build` → `29 modules transformed`、`built in 305ms`，exit 0。 |
| **T1 三态 375×812** | 2026-11-12 | 设备模拟（CDP `Emulation.setDeviceMetricsOverride` width=375 height=812 dsf=2）+ `Page.captureScreenshot`，产物 `docs/reports/ui-t1/{01-empty,02-loading,03-error}.png`（750×1624 = 375×812@2x）。三态均 `innerWidth=375`、`document.documentElement.scrollWidth=375`、`.panel` 右边界 351 < 375 → **无横向溢出**；empty 态正文折 2 行、卡片右描边完整可见。 |
