# T5d · 拍照上传建档链路

当前：D1真实门闸与D2九张真实浏览器上传均通过，T5上传链路完成。本报告不把额外门闸、断网故障或缓存重传算进九张样本。

## D1 真实门闸（2026-11-13）

- 路径：真实TestClient multipart POST→client.vision（qwen3.8-omni-flash，item_extract.v2）→既有解析/校正→data/app.db。无脚本化模型响应或mock分支。
- 图片：cases/images/cloth01.jpg；HTTP 201，客户端整请求5708ms。SQLite count实际14→15，同draft重传HTTP 200/reused=true，count仍15。
- 来源：confidence、warmth为model；id/确认状态为derived。sources._corrections={source:derived,entries:[]}确实存在并与响应一致；本次未触发校正，不伪造非空日志。
- 幂等：draft_id=a032ac9e-3114-455b-8941-f2854d50f3c9，item_id=Ua032ac9e3114455b8941f2854d50f3c9-00；已成功重试直接读库，不新增识别调用或单品。
- 可核对原文及SQLite快照：[D1门闸](raw/upload/d1-gate.json)。门闸记录保留在库中，后续九张采用各自独立草稿ID。

## 接口与持久化口径

- POST /api/wardrobe/items：multipart字段photo、draft_id(UUID)。首次201，成功草稿重试200；同draft换图409。支持JPG/PNG/WebP，照片不超过10MB。
- 响应含items、corrections、latency_ms、prompt_version、draft_id、reused。sources普通字段仍为user/model/derived；保留元数据区_corrections存derived校正记录，_upload存derived草稿ID及照片SHA256，未新增数据库列。
- 图片仅存data/uploads；GET /api/wardrobe/items/{id}/photo仅可读上传目录。照片失败回滚、不创建半套单品；同draft跨进程文件锁与确定ID保护重试，多item事务提交。
- 五类模型错误沿用auth/rate_limit/timeout/parse/network。最多3次识别调用；超时不自动重试，返回“请手动建档”并说明入口尚未开放。低置信度使用唯一derive_needs_confirm规则；PATCH复用五字段白名单，保留校正审计。

## 手动入口边界

本轮失败保留照片/占位并可原地重试，不创建手动录入表单。触发条件、D10属性提问与来源裁决见[backlog](../backlog.md)：真实用户测试≥2次识别失败，或演示需要无网场景时再启动；禁止给warmth/formality/seasons填猜测默认值。

## D2 九张真实完整建档（2026-11-13）

- 环境：人类终端的`zsh -ilc 'make dev'`，真实Chrome CDP设备模拟375×812、DPR=2；前端5173→Vite代理→后端8000→`extract_photo`→真实`client.vision`→SQLite提交→读取本地照片→新卡片绘制。未注入这九次模型/HTTP响应。
- 模型：`qwen3.8-omni-flash`；prompt：未修改的`prompts/item_extract.v2.md`。响应完成时间窗23:06:30–23:07:26（+08:00）。R01–R08用文件选择，R09用真实浏览器File/DataTransfer拖放事件触发相同上传入口。
- **完整单张建档计时**：浏览器`performance.now()`从设置所选文件/触发拖放前，到返回的新卡片照片加载完成且经过两次requestAnimationFrame；包含上传、模型全部调用/重试、校正、落库、照片获取与页面更新。**不含拍摄、打开系统相册或人工选择时间，也不是首次10张建档总耗时。**
- 9/9成功，各新增1件；服务端访问日志均201 Created，响应均`reused=false`；每次恰好1次模型调用，无自动重试。逐条响应/草稿ID/来源/卡片及视口记录见下表链接，[完整浏览器记录](raw/upload/browser-nine.json)。

| 样本/原文 | 照片 | 实际品类/子类 | 完整建档ms | 服务端ms | confidence | corrections |
|---|---|---|---:|---:|---:|---|
| [R01](raw/upload/R01-upload.json) | cloth01.jpg | outer / 连帽冲锋衣 | 6278 | 6162 | 0.98 | `[]` |
| [R02](raw/upload/R02-upload.json) | cloth02.jpg | top / 拉链长袖短款上衣 | 6635 | 6580 | 0.95 | `[]` |
| [R03](raw/upload/R03-upload.json) | cloth03.jpg | bottom / 松紧腰阔腿裤 | 6314 | 6246 | 0.95 | `[]` |
| [R04](raw/upload/R04-upload.json) | cloth04.jpg | top / 半拉链短袖T恤 | 7015 | 6951 | 0.98 | `[]` |
| [R05](raw/upload/R05-upload.json) | cloth05.jpg | top / 长袖衬衫 | 6632 | 6517 | 0.95 | `[]` |
| [R06](raw/upload/R06-upload.json) | cloth06.jpg | bottom / 工装短裤 | 5411 | 5277 | 0.98 | `[]` |
| [R07](raw/upload/R07-upload.json) | cloth07.jpg | bottom / 运动短裤 | 6248 | 6149 | 0.98 | `[]` |
| [R08](raw/upload/R08-upload.json) | cloth08.jpg | shoes / Air Jordan 1 Low运动鞋 | 8880 | 8761 | 0.98 | `[]` |
| [R09](raw/upload/R09-upload.json) | cloth09.jpg | shoes / Nike Ja 2 Low EP 篮球鞋 | 6431 | 6315 | 0.98 | `[]` |

**完整单张建档5411–8880ms，n=9；服务端5277–8761ms，n=9。** corrections为0/9张、0条；每件`sources._corrections={source:derived,entries:[]}`均真实落库，confidence保持model来源，无任何静默修改。本批未触发非空校正或低置信度，不能拿9/9接口成功冒充识别属性准确率；非空校正来源与低置信度编辑解锁由离线测试覆盖。

## SQLite、重试与三态证据

- 直连`data/app.db`，正式九张前15件→后24件；每个draft恰好1行，9条sources与API逐项一致，照片SHA256与本地文件一致。库中15件起点包含14件基准衣柜和D1额外门闸，保留门闸不清库。
- 对九个成功draft分别带同一照片再次POST：全200/reused=true、返回同一items；库24→24，模型调用日志9→9。不同draft上传相同照片属于不同建档操作，幂等按draft区分。逐条库快照、缓存响应及原模型日志见[SQLite核查](raw/upload/sqlite-nine.json)。
- 实际检查输出：

```text
SQLite count: 15 -> 24; cached retries: 24 -> 24
model attempts: 9 -> 9; one row per draft: 9/9; sources/photo SHA256 match: 9/9
corrections: 0/9 photos, 0 entries; needs_confirm: 0
```

- [断网保留证据](raw/upload/ui-offline.json)：CDP真实断网，点击原地重试仍使用同一File/draft_id；input仍选中cloth01.jpg、预览及错误占位保留。两次均不联网，不计模型样本；随后恢复联网，九张验收另用新draft。
- loading/失败/成功截图为真实上传路径：[上传骨架](ui-t5d/01-uploading.png)、[错误保留与重试](ui-t5d/02-error-preserved.png)、[成功卡片高亮](ui-t5d/03-success-highlight.png)。9张卡片均立即高亮，R01另实测2.1s后高亮关闭；浏览器Runtime异常0。
- 衣柜GET的[loading](ui-t5d/04-wardrobe-loading.png)/[empty引导](ui-t5d/05-empty-guidance.png)另以CDP暂挂GET/注入空数组验视觉，明确为UI故障注入，不改生产库、不计真实模型样本；[状态说明](raw/upload/ui-states.json)。所有截图已逐张检查，设备内innerWidth=scrollWidth=375、height=812，无横向溢出。
- `zsh -ilc 'make test && make lint && cd web && npm run build'`：`244 passed in 1.27s`、Vitest `Tests 15 passed (15)`、`All checks passed!`、tsc exit0、`built in 290ms`。新增6条前端测试覆盖失败保留/原地重试/合并去重/无效成功响应及旧GET晚成功/晚失败的竞态，原有测试未删改。
- 冻结清单`docs/reports/t5d-freeze.json`核查134个旧证据/prompt/cases文件SHA256全不变；本轮D2代码仅`api.ts`、`api.test.ts`、`Wardrobe.tsx`。无新前端依赖、页面内直接fetch或mock生产开关。

## 重现入口与未验收边界

```bash
make dev
# 浏览器打开 http://127.0.0.1:5173/，设备模拟375×812，逐张选择cases/images/cloth01.jpg … cloth09.jpg
# 同一草稿重传示例：用raw/upload/R01-upload.json中的draft_id，不要重新生成ID
curl -sS http://127.0.0.1:8000/api/wardrobe/items \
  -F 'photo=@cases/images/cloth01.jpg' \
  -F 'draft_id=77d9b552-2379-4ba1-ae60-f34d65fa08d8'
sqlite3 data/app.db 'select count(*) from wardrobe_items;'
```

缓存重传不会产生新模型调用；新草稿重新实测会消耗额度、追加新单品。`data/app.db`/`data/uploads`均忽略提交，原始九张与可审计响应保留在仓库。

未做真实非衣物上传（A素材仍pending）、10张首次建档/相册操作总计时、P95、人工可穿率、手动建档、T9或完整60秒录屏。首次录入≤3分钟/10张≤90s仍不能由此次逐张n=9推定。T12因T9/完整录屏保留🟡。
