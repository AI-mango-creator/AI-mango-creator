# T21 Try-on Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. User approved A→B→C continuous native execution; do not ask again for this sequence.

**Goal:** 首页体验服饰目录与私有异步真实试穿接口，当前仅离线验收。
**Architecture:** SQLite目录/job/匿名当日提交账本；唯一client用原生FASHN REST，浏览器只调自有API；不引入worker/SDK。
**Tech Stack:** 既有FastAPI/Pydantic/httpx2/React/TypeScript。
**Spec:** docs/superpowers/specs/2026-11-19-tryon-experience-design.md

## Global Constraints
A7/B8/C8，每段全量test/lint后提交；无key/预算本轮不发真实调用。独立AGENTS限定例外与D14先提交。旧cases/prompt/134冻结证据不改；无新依赖。只有有权素材可导入，目录默认空。原衣柜/社区/编排不改业务。

## Review Focus
删除后旧提交拒绝、不重复收费；午夜和等锁过期；提交结果未知不重发；清空时晚回包不重建照片；前端旧设备/旧页面响应不串图。

## 0 Rules
- [ ] AGENTS单独增加T21限定例外；D14单独记录第三能力预算及本轮无真实调用。

## A Data/catalog (7)
Files: app/models.py, app/migrations/008_tryon.sql, app/db.py, app/tests/test_db.py, app/tests/test_tryon_db.py, scripts/import_tryon_catalog.py, app/tests/test_tryon_catalog.py.
Interfaces: models新增ExperienceProduct/TryonJob/TryonView/ProviderTryon/TryonTicket；db.issue_tryon_ticket(path,owner,product_id)和reserve_tryon(path,owner,product_id,ticket,digest)→(job,reused)，quota+ledger+job原子；同票同hash重用、异hash409、删除后410、到期拒绝。
- [ ] 写临时库RED：迁移幂等、同请求不重复计额、清空job后410、跨owner/午夜ticket无效、每设备3次与分享10次，来源字段。
- [ ] 写导入RED：dry-run不写、有权说明必填、apply幂等、冲突报错、非法图片不写。
- [ ] 实现008两表及额度两列，只扩展DailyQuota与新协议，旧字段不改。脚本仅本地文件，复制至uploads/catalog；默认不导入任何素材。
- [ ] 全量make test/lint，补tasks/CHANGELOG，提交。

## B Client/API (8)
Files: app/llm/client.py, .env.example, app/services/tryon.py, app/routers/tryon.py, app/main.py, app/routers/wardrobe.py, app/tests/test_tryon_api.py, app/tests/test_tryon.py.
Interfaces: client.tryon_submit(person,garment,category), tryon_status(task_id)，纯Pydantic响应；service提供products/photo/ticket/create/get/delete/clear；routes /api/experience/products 与 /api/tryons。所有job/结果按owner，服务默认真实client，测试注入client函数。
- [ ] RED测试：未配置/401/429/未知提交超时不重发、解析、完成结果、本机图片保护、重复提交、轮询节流、删除/清空晚回包。
- [ ] 增加client原生REST，不动chat/vision；每HTTP≤20s，一次生成POST，最多30次状态GET/120s，不自动重发生成；input/output base64，不记录照片/key。
- [ ] service在网络前后分别短事务，不持DB写锁联网；落图前存在性复查，清空同owner_lock，无复活。公共状态不暴露供应商id/路径。清空保留匿名账本/计额。
- [ ] 全量make test/lint，补tasks/CHANGELOG，提交。

## C Frontend (8)
Files: web/src/pages/Home.tsx, web/src/pages/ProductDetail.tsx, web/src/components/ExperiencePhoto.tsx, web/src/lib/tryonApi.ts, web/src/lib/tryonApi.test.ts, web/src/lib/tryonView.ts, web/src/lib/tryonView.test.ts, web/src/styles.css.
Interfaces: products/getProduct/issueTicket/createTryon/getTryon/recentTryons/photo资源管理；getTryonView纯状态映射。
- [ ] RED Vitest：设备头、multipart/相同ticket重试、照片ObjectURL释放/旧响应忽略、状态/超时、结果仅真实completed显示。
- [ ] 替换首页个人图墙/上传快捷为体验目录，明确暂无合作，不编价格；保留衣橱数量和AI入口。
- [ ] 详情选择本人照片并确认处理说明；保留失败输入，processing禁重复/仅0或1进度，旧ticket过期需用户重新确认；显示真实结果/回到原图，删除任务；无key中文。
- [ ] 全量make test/lint/build，补tasks/CHANGELOG，提交。

## Final
- [ ] Fresh independent review; fix with regressions within approved scope≤8。
- [ ] 临时DB/两设备、375×812真实本地API；测试供应商注入仅限隔离QA进程且截图明确“离线注入，非真实试穿”。正式目录仍空，无私有人像入Git。
- [ ] 报告确切测试/无溢出/冻结SHA，T21🟡待真实素材/账号/费用确认；按已有授权no-ff合main，不自动同步GitHub。

Ruling: A使用独立tryon_daily_quotas而非给daily_quotas加列：旧测试合法依赖五列无列名INSERT，原表加列会破坏兼容且不准改旧断言；新表仍匿名/次日过期/清空保留，同事务能力不变，文件仍A7。若错将增加一张表的维护成本，不影响原额度。

A complete: 新增6测试；379 pytest+57 Vitest、lint和导入脚本ruff通过。旧5列无列名INSERT保持；本地auto-reload早期008已建额外列，备份data/backups/t21-pre-reconcile.db后以纯CREATE补齐最终表，旧业务计数不变，额外列不删除。

B complete: 13新增后端测试，392 pytest+57 Vitest/lint通过；恢复submitting与日志等不确定错误先RED后GREEN，不重复生成。

C implementation: 392 pytest+64 Vitest、lint/build467ms，8文件，最后独立审查和375px正在进行。

Final: fixed new-attempt re-ticket after lost response — TryonAttempt regression RED→GREEN and CDP 2→2 injected generation calls; fixed polling recovery — CDP before3/after3 RED, final manual-query recovery GREEN. Configuration UI and task log correlation also RED→GREEN. Final suite394/394 backend+65/65 frontend, lint/build383ms; 23 screenshots375x812, Runtime0, 134 frozen SHA unchanged. No deferred minors. Real provider calls0; T21🟡 awaiting resources. Native execution kept approved scope, repair6 code files.
