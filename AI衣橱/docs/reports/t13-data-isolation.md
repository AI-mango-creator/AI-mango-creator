# T13 · 隔离、配额与确认验收

本报告逐段追加；不覆盖T5d或v1/v2/v3等冻结证据。当前T13 A/B/C全部完成；只读审查发现项已修复并以RED→GREEN及最终真实浏览器验证。历史probe适配明确保留backlog。

## A1 · 幂等迁移与legacy（2026-11-13）

- 六个代码文件：models、db、002_owner_scope.sql、seed、claim_legacy、test_db。owner_id为derived，默认legacy仅供迁移/离线基准，四表均NOT NULL；cases/prompt字段不变。
- 旧001库迁移、连续重复迁移、8次并发启动、双设备seed、跨owner关联拒绝、NULL拒绝、认领dry-run只读/apply四表与重复apply均有临时库测试。
- 真实库已先用SQLite backup保存到`data/backups/t13-before/app.db`，然后连续执行两次`init_db`：

```text
migration twice: {"wardrobe_items": 24, "sessions": 2, "outfit_sets": 6, "outfit_items": 18} all owner=legacy; original fields preserved; version= 2
rollback backup: data/backups/t13-before/app.db
dry-run（未写库）：wardrobe_items=24，sessions=2，outfit_sets=6，outfit_items=18
```

- 24件没有跳过、认领或丢弃；原ID/属性/图片路径逐项一致，仅新增owner及derived来源标签。真实库未执行`--apply`。详情见[t13-a1-migration.json](t13-a1-migration.json)。
- 单测从5条RED进入GREEN，既有四表字段校验保留，同时对新增配额表逐字段校验。旧SQL不改、不DROP，版本号与新DDL同事务；幂等不重复加列或灌数据。
- A1通过250 pytest + 15 Vitest，make lint通过；134冻结文件哈希不变。

### A1回滚与重建（仅本地开发，命令未执行）

先Ctrl-C停止make dev。A1尚未移动或删除旧照片，备份库对应原data/uploads内容。

```bash
# 恢复A1前代码和完整24件库；确认工作区无未提交内容后执行
# 8e18d03是T13前基线
 git switch --detach 8e18d03
 cp data/backups/t13-before/app.db data/app.db
 make dev
```

备选重建（只恢复基准数据，不恢复24件上传/编辑/历史方案，不作为保留数据的回滚）：停止服务，先另存当前库，再执行`make seed`。

```bash
mv data/app.db data/app.db.t13-saved
make seed
```

回滚/重建均不DROP。新代码再次启动会重新迁移，因此完整回滚须同时恢复旧代码。实际备份与data/uploads均在.gitignore内，不提交数据库/照片。

## A2 · 隔离、匿名配额与清空

- 代码8文件：main/db/wardrobe/outfits、三份API测试及health测试。health仅新增临时库夹具，防止启动清理测试触碰真实库；不改原健康检查断言。
- X-Device-ID必填UUID，缺失/非法/legacy/重复头拒绝400。四表所有请求SQL与写入都绑定owner，照片读取也校验owner，上传草稿/目录/ID按owner隔离；不提供缺省返回全部的路径。
- owner级文件锁覆盖上传/编排/PATCH/清空，识别在途时清空等待，避免删除后旧请求回写。锁名也是加盐hash，清空后不残留UUID目录。quota仅hash，不放UUID进计数表；盐data/.quota_salt权限0600，跨进程读同一盐。
- 当前日按Asia/Shanghai计数；20张识别、30次编排，启动模型前事务预占，失败仍计一次；内部重试/缓存重传不重复计数，候选不足不计。并发24次仅20次成功、4次429；次日归1且过期行删除。启动先清理过期，运行中午夜后台清理，业务请求也兜底清理。

### 真实模型与持久化验收

真实TestClient分别上传cloth01/cloth02，均走既有client.vision、v2 prompt，没有模型注入。A建档后B列表为空，B自行建档后两边各只见自己的1件；B读A照片与PATCH均404。随后仅为开发验收显式给A seed14件，再真实POST编排，生成3套且所有item归A。

```text
REAL A/B: uploads 201/201; B before own upload=[]; cross photo/PATCH=404/404
REAL A before clear: {'wardrobe_items': 15, 'sessions': 1, 'outfit_sets': 3, 'outfit_items': 12} -> {'wardrobe_items': 0, 'sessions': 0, 'outfit_sets': 0, 'outfit_items': 0} ; B preserved: {'wardrobe_items': 1, 'sessions': 0, 'outfit_sets': 0, 'outfit_items': 0}
REAL quota retained after clear: (1, 1) ; legacy unchanged: {'wardrobe_items': 24, 'sessions': 2, 'outfit_sets': 6, 'outfit_items': 18}
```

A照片删除、B照片仍可读取；最后单独清理B验收数据，legacy24件及原方案/会话不动。A当日计数识别1/编排1在清空后保留，次日过期。完整响应/owner/SQL结果见[t13-a2-real.json](t13-a2-real.json)。

### 配额与故障注入验收（离线，不冒充供应商429）

`pytest -q -s app/tests/test_owner_isolation.py`：识别20次成功/缓存重传200/第21次429且调用20次；编排30次成功/第31次429且调用30次；B缺件不扣编排。测试客户端层注入真实响应格式，验证的是本系统额度与隔离，未实际消耗50次模型调用。

共13项新增用例覆盖缺标识、legacy、跨设备草稿/照片/PATCH、双配额、删除全部业务及照片保留另一设备、并发上限/盐跨进程持久化/日界、失败仍扣、清空不能绕限、在途识别与删除串行、启动清过期。全量263 pytest + 15 Vitest与make lint通过，之后才进入A3。

隐私说明见[08-隐私政策](../08-隐私政策.md)：使用额度记录保留至次日 0 点，不含照片与衣柜内容。真实验收UUID只是本地测试设备标识，报告不是运行时用户数据表。

## A3 · 唯一设备模块与浏览器隔离

- 七个代码文件：deviceId及测试、api及测试、outfitsApi及测试、Wardrobe。只有deviceId.ts读取localStorage；首次生成UUID并持久化、重复读取稳定、非法/legacy替换、存储被拒绝给中文错误，不悄悄用临时设备。
- GET/PATCH/上传/DELETE/编排/照片均带同一X-Device-ID；照片经api.ts带头取blob、组件负责释放ObjectURL，不在图片URL中附设备ID。衣柜/上传/PATCH/编排响应防御性核查归属。
- 真实CDP两个隔离上下文：A新设备初始空（legacy未泄漏），仅开发显式seed给A14件后，A=14、B=0；刷新后UUID不变。两者innerWidth=scrollWidth=375，height812，Runtime错误0。此步未调用模型。
- 证据：[t13-a3-browser.json](t13-a3-browser.json)、[A衣柜](ui-t13/a3-owner-a.png)、[B空衣柜](ui-t13/a3-owner-b-empty.png)。新设备A的14件是此次明确dev seed，不是认领旧24件；旧24件仍legacy。
- 全量263 pytest + 25 Vitest、make lint及build通过；A隔离部分完成，随后才进入D10-b。前端增加10条测试（相对原15条），不引DOM测试环境或新依赖。

跨日额外实测：北京时间2026-11-14 00:00:46查询真实库，A2清空后保留的两个当日配额行已自然清为0，未手工reset。见[t13-midnight-expiry.json](t13-midnight-expiry.json)。

## B决策与后端（D10-b先行）

- 决策单独提交`7099171`仅含decisions.md，再改运行代码。保留D6/D8历史原文，由D10-b明确覆盖上传阈值规则；D9仍指鞋过滤豁免，outer一致性校正的实际实现边界按extract.py说明。
- 唯一derive_needs_confirm只看uploaded/user_edited，confidence完全退出放行条件；识别结果不论0.1/0.6/0.95/1.0均待确认。旧8个阈值测试输入均保留，只依决策把0.6/0.7/1.0的期望改为true，未删除或跳过测试。
- PATCH五字段任一与POST /api/wardrobe/items/{id}/confirm均走模型确认方法，置user_edited、派生needs_confirm；确认不伪造属性修改，confidence/category/sub/warmth等值与来源不变，corrections审计保留。确认幂等、按owner查写，额外属性body拒绝422。
- 003迁移只回填有_upload审计且未user_edited的历史记录；真实legacy中10件旧上传均变待确认，14件基准不受影响，原24件归属仍legacy。迁移重复执行不重复改写或新增行。
- 三条后端抗体先RED（高置信度错类目旧规则直接放行、确认路由缺失、历史未回填），实现后转绿；新增六个置信度输入测试及非上传不入队测试。全量274 pytest + 25 Vitest与lint通过后进入前端；九张真实重跑留下一段。

## B前端与九张真实重跑（2026-11-14）

- “这是对的”经api.ts发确认请求；五字段编辑仍走PATCH；失败保留原卡片状态并显示中文错误。确认按钮与编辑按钮为article内同级元素，未嵌套button。模型置信度仅在编辑详情辅助展示。
- 真实浏览器/模型仍为qwen3.8-omni-flash、原item_extract.v2，无新prompt/模型替换/旧录制重放。九张首次入库均待确认（9/9），R01通过界面PATCH子类、R02–R09逐个点击“这是对的”，刷新后9/9为false，confidence不改且来源仍model。

| 样本 | confidence | 初始needs_confirm | 确认后 | 动作 | 首调服务端ms | 模型尝试数 |
|---|---:|---|---|---|---:|---:|
| [R01](raw/t13-confirmation/R01.json) | 0.98 | true | false | PATCH sub | 缺失，见恢复说明 | 3 |
| [R02](raw/t13-confirmation/R02.json) | 0.95 | true | false | 这是对的 | 6729 | 1 |
| [R03](raw/t13-confirmation/R03.json) | 0.95 | true | false | 这是对的 | 10579 | 2 |
| [R04](raw/t13-confirmation/R04.json) | 0.98 | true | false | 这是对的 | 5372 | 1 |
| [R05](raw/t13-confirmation/R05.json) | 0.98 | true | false | 这是对的 | 6375 | 1 |
| [R06](raw/t13-confirmation/R06.json) | 0.98 | true | false | 这是对的 | 4298 | 1 |
| [R07](raw/t13-confirmation/R07.json) | 0.98 | true | false | 这是对的 | 7261 | 1 |
| [R08](raw/t13-confirmation/R08.json) | 0.98 | true | false | 这是对的 | 6447 | 1 |
| [R09](raw/t13-confirmation/R09.json) | 0.98 | true | false | 这是对的 | 6347 | 1 |

- 首张验收驱动在截图期间超时，浏览器页面发生刷新；其真实模型路径先两次network失败、第三次成功，已入库。没有重识别首张：按相同draft缓存读取（HTTP200/reused=true）恢复证据，模型总尝试仍3。首调HTTP结果与浏览器/服务端总耗时没有完整保留，明确记缺失，不用缓存耗时替代、不剔除这张。
- 总计9个建档请求占识别额度9，实际模型尝试12（各≤3）。原图、草稿、响应/恢复说明、置信度、确认动作及SQLite逐项核查见[完整浏览器记录](t13-confirmation-nine.json)、[SQLite与调用日志](t13-confirmation-sqlite.json)。corrections本轮仍全空，空审计仍落库；没有拿这个结果声称校正分支真实触发。
- R02本轮仍误判top、confidence=0.95，但待确认已正确触发。自动化点击“这是对的”仅验证确认通路，**不代表人工认可九张属性正确，也不记为识别准确率提升**；没有改prompt或case去修饰分类表现。
- 真实照片请求全部携带本设备头，跨刷新同owner，Runtime错误0，375×812无横向溢出。[待确认截图](ui-t13/b-02-pending.png)、[确认后截图](ui-t13/b-03-confirmed.png)为C文案变更前证据，卡片UUID将在C去掉。
- 全量274 pytest + 27 Vitest、make lint/build通过后才进入C。旧134个冻结文件不变，旧T5d报告与照片证据也未覆盖。B代码仅Wardrobe/api/api.test三文件。

## 最终只读审查与A层修复

审查复现发现原T13-ID含设备UUID、业务响应缺少no-store、额度在等待锁前采样日期，以及编辑无变化时伪造category PATCH。已暂停C，拆成A层6文件/B层3文件分别回归，禁止把四项塞进C超过文件限额。

A层先新增RED抗体，复现仅凭单品ID恢复设备归属、照片/衣柜缓存头缺失、SQLite等待跨午夜把新调用记回昨天；另验异常500也禁止缓存。修复后：

- 新上传用随机opaque ID；开发seed用服务端盐的稳定opaque映射，不在URL或模型候选ID携带设备UUID。
- 004只迁此前含设备UUID的owned ID，父子关联同事务映射，推迟外键检查至提交；无DROP、不增加数据表/删字段。legacy24件原ID及全部属性不变。
- 真实库先备份`data/backups/t13-before-opaque/app.db`；迁移两次，总47→47，owned23条改opaque，外键违规0。九张上传按不变draft_id关联新旧ID，确认/置信度/来源/图片路径均不变，见[t13-a-reviewfix.json](t13-a-reviewfix.json)。B九张报告保留当时旧ID，不覆盖；当前API读取应使用新ID。
- 所有业务响应含Cache-Control:no-store与Vary:X-Device-ID，非法设备/404/500亦覆盖；照片不会由标准共享缓存跨owner复用。
- 配额日期在取得SQLite写锁后计算；可控午夜+真实锁阻塞复现现写入2026-11-14，而不复活2026-11-13行。
- 全量279 pytest + 27 Vitest、lint通过，接着处理B层确认来源。永久设备hash锁文件因涉及清空后的标识残留，按用户隐私约束重判为需要修复：改固定64桶，1000随机UUID仅64文件；停服后清理本地旧hash锁3个。仅历史probe未适配保留backlog。

锁文件补充实测：`1000 random device IDs: persistent lock buckets=64 (cap64); no per-device hash filenames`。此项作为隐私生命周期修复完成，不列为延期minor。

B层审查修复：保留空PATCH在后端422的契约；编辑待确认单品未改字段时，前端传空修改集给api，api改走POST confirm，不再制造同值category PATCH。新增客户端RED测试先复现走错路由，再验证确认后category来源仍model。当轮279 pytest + 28 Vitest通过，但lint发现新测试fixture的TS类型推断错误；在读取结果前过早推进了提交。恢复C时已补显式类型注解并保留合并两边测试，最终279 pytest + 29 Vitest、lint/tsc均通过；真实浏览器也补验该入口。

## C · 最终界面、失败文案与验收

- 五代码文件：Wardrobe、api及测试、extract、test_wardrobe_api。卡片副标题为“品类 · 子类”，opaque ID仅编辑详情；没有把ID从数据协议删掉。上传超时与网络错误使用用户可读重试提示，删除未开放手动入口的文案；失败照片、原生input与草稿原地重试保持。
- 后端新文案断言与前端断网文案先RED，再实现转GREEN；C合并时发现的fixture TS2322与测试尾部冲突已修复，双方新增用例均保留。
- 最终真实CDP五张375×812@2x截图均已逐张查看：[卡片无ID](ui-t13/c-01-card-no-id.png)、[编辑详情ID/辅助置信度](ui-t13/c-02-edit-id.png)、[断网保留与重试](ui-t13/c-03-error-preserved.png)、[loading](ui-t13/c-04-loading.png)、[另设备真实empty](ui-t13/c-05-owner-b-empty.png)。各态innerWidth=scrollWidth=375；Runtime错误0。
- 编辑未改保存补验：仅将QA设备R02暂时复位为待确认（未新调模型，未改属性/来源），真实界面点击“确认并保存”只发POST confirm、无PATCH，确认后category来源仍model、needs_confirm=false。此为状态注入，不算新识别样本；九张确认结束状态仍9/9 false。
- loading只暂挂真实GET、不伪造返回；empty来自独立设备B实际空衣柜；断网连续两次保留同File/input/draft，随后恢复网络，不重传至模型。首张识别中断的导航竞态仅修验收驱动：等待新文档timeOrigin与页面加载完成再操作，未加产品mock开关。
- 浏览器实测输出与请求/状态明细见[t13-c-browser.json](t13-c-browser.json)、[QA复位说明](t13-nochange-confirm-setup.json)：

```text
cards_hide_ids=true; detail_has_id=true
nochange_method=POST confirm; category source=model
retained_file=cloth01.jpg; retry_same_draft=true
cache_control=no-store; vary=X-Device-ID
A/B/loading: width=375 height=812 scrollWidth=375; errors=[]
```

- 最终命令`zsh -ilc 'make test && make lint && cd web && npm run build'`：279 pytest、29 Vitest、ruff/tsc通过；build308ms（后续仅文档变更）。每段均先全量pytest后进入下一段，没有将失败测试删掉、skip或xfail。
- 四项主要审查问题（ID泄漏、缓存隔离、跨午夜记账、无改动确认来源）与锁文件隐私生命周期问题均有失败复现及修复后回归；未做第二轮重复审查，以覆盖测试与真实浏览器校验关闭问题。审查未重复现场模型/午夜/截图，以本次已落盘证据为准；R01缺失首调总耗时不可从缓存还原、R02状态验收不代表分类正确，两项边界继续保留。

## 最终数据与未做项

A2真实隔离/清空设备已分别清为四表0；它们不同于A3新浏览器设备。当前本地开发库总47件=legacy24件+新浏览器QA设备23件（显式dev seed14+新拍照9），没有清空后在途回写。旧24件没有自动归给新设备。SQLite备份与上传均忽略提交，仅本地开发验收用。

未部署、未接Capacitor/Keychain、未做注册登录/手动录入/T9；未改模型/prompt或case标准；未重跑冻结v1/v2/v3评测；未重测含人工确认的完整首次建档时长/P95/穿搭盲评。历史e2e_probe无设备头，仍不作为可用验收入口，具体修复触发条件见backlog。隐私说明已明确额度记录次日0点到期。

最终保护检查真实输出：134冻结文件及旧T5d证据不变；prompts/cases/client/dependencies/AGENTS无diff；60个文档链接有效；secret/base64扫描clean；完整make test前后真实数据库SHA256不变；C代码文件5个。
