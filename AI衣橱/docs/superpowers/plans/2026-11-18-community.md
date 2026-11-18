# T20 Community Implementation Plan

> 执行superpowers:executing-plans；用户已批准A→E范围并连续实施，自行顺序执行，不重复询问确认。

Goal：真实发帖/关注/点赞/评论/投票与社区导航，私有衣柜保持隔离。
Architecture：SQLite八张社区表，models唯一协议；public副本与private表分离，设备代号不公开；原生React状态和API，无依赖/AI调用。
Spec：docs/superpowers/specs/2026-11-18-community-design.md。

Global：A4/B6/C3/D8/E≤7；每段全量test/lint；不放宽旧测试、cases或134冻结项；最终双设备真实API及CDP375×812；按授权no-ff合main，不发布。

Review Focus：事务和文件撤回失败可重试；公开响应无私有字段；并发/重试唯一投票/评论/发布；清空保持配额和他人内容；切页取消/失败保留草稿和ObjectURL释放。

## A 数据（4）
models.py定义DB与公开响应/创建草稿；007_community.sql创建八表/唯一索引/FK；test_db.py精确增加全部字段检查；test_community_db.py验证幂等/唯一/FK。先RED，再实现，全量验证提交。

## B 帖子与清空（6）
services/community.py实现身份、列表游标、发布hash幂等、图片副本、owner校验、删除暂存恢复、clear_for_owner；routers/community.py只承接设备依赖/参数/上传/图片；main注册；test_community_api.py/test_community_clear.py用tmp_path；wardrobe.clear_items复用同一connection清理。先404/缺模块RED，再全量GREEN提交。

## C 互动（3）
community服务/路由+test_community_interactions.py。PUT赞/关注幂等；评论client_id防重；vote唯一不可改，option属于该帖，COUNT计算真实计数。先RED，再GREEN全量提交。

## D 列表与导航（8）
App/BottomNav/AppIcon/Community/CommunityImage/communityApi/communityApi.test/styles。导出PublicPost/Comment/Draft类型和CRUD；四tab、分页、作者/图片、明确空错载入；搭配底栏归属衣橱。API/媒体释放/草稿校验测试先RED再GREEN提交。

## E 详情发布（≤7）
Community/PostDetail/PostComposer/Outfits/communityApi/communityApi.test/styles。发布类型弹层及四种编辑、草稿ID与File保留，真实互动/评论/图片组、本人删除、PK与多选项投票。沿用API测试并浏览器验证。

## Final
独立只读whole-branch审查，一次修复并全量回归；两个设备上下文真实社区API，不注入社区假响应，故障注入明确标记；所有页面375×812多态截图。记录旧355+50与新增结果、冻结SHA、无LLM、隐私检查、任务状态；合入main并清理仅自有QA进程。

## Ledger
2026-11-18 人类已批准全部阶段。AGENTS/决策各独立提交。开始A，尚未宣称实现。

A complete：357 pytest+50 Vitest、lint通过，4文件。

B complete：364 pytest+50 Vitest、lint通过，6代码文件。公开照片读出字节避免撤回时FileResponse竞态，feed使用一致读事务。

C complete：367 pytest+50 Vitest、lint通过，3文件。

D complete：367 pytest+56 Vitest、lint/build350ms通过，8代码文件。

E implementation：367 pytest+57 Vitest、lint/build364ms通过，7代码文件。最终审查/真实双设备浏览器待验。


Final complete（2026-11-19）：whole-branch审查后修复4代码文件；新增6后端回归均先RED后GREEN，包含1100层ANMF恶意输入422，复审无阻断。373 pytest+57 Vitest、lint/build426ms。双设备真实社区23检查+6补验、34截图无溢出/Runtime0；清空A保留B与当日匿名额度、93个ObjectURL全释放。134冻结SHA不变，无LLM/天气调用。报告reports/t20-community.md；合入本地main按既有授权执行，不同步GitHub/隧道。
