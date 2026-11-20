# T22 我的中心、真实积分、收藏与私密 OOTD

日期：2026-11-20。状态：人类已批准完整设计与A→F连续实施；2026-11-20完成，验收见docs/reports/t22-personal-center.md。

## 已确认目标

按本轮五张参考图完善底部“我的”：粉色渐变个人抬头、从左到右的档案/积分/消息/设置入口、关注/粉丝/互动统计、圆角白色内容区和双列内容卡。积分明细、收到的互动及浅灰蓝底设置页沿用参考图的信息层级和留白；375×812基准、最大480居中。参考图只作布局参考，不复制他人头像、用户名、手机号、积分、试穿效果、品牌或备案信息。

人类已确认两项范围：

1. 真实每日积分，允许修订AGENTS积分限制；每设备每天首次访问+10，余额与流水持久化，不做邀请奖励、充值或抵扣AI调用。
2. 真实收藏社区帖子；真实OOTD，可按日期保存自己的穿搭照片或衣柜搭配记录，默认私密。

沿用当前设备身份；无注册登录、手机号或多设备找回。现有身材档案保留为独立子页。真实试穿仍受T21原有资源/费用确认限制，本轮不发生模型/试穿调用，不补假历史。

## 方案与取舍

- 纯截图原型：能还原版式，但积分/收藏/OOTD不落库；人类已选择真实功能，排除。
- **沿用设备身份的真实个人中心（采用）**：扩展现有SQLite和本地文件，复用真实社区/搭配/试穿记录，保持make dev启动方式；能完成本轮需求，但更换浏览器或清除设备ID后不能找回原资料。
- 完整注册登录与会员中心：需要新的账号、认证、找回和运营规则，超出当前批准范围，排除。

下述收藏对象、OOTD编辑方式、清空语义及设置中的可用项目是实现者提案，随本文一次确认；不是声称人类已逐项指定。

## 页面与操作

### 我的首页

顶部显示本人昵称与私有头像（未上传时为应用占位图标），依次为“我的档案”“N积分”“消息”“设置”。头像和昵称可在设置中修改。昵称与本人社区作者名一致；头像首版仅用于个人中心，不因上传头像自动公开人物照片。

关注/粉丝点击查看真实作者列表，可进入其公开帖子；互动计数定义为别人对本人帖子的当前点赞+评论+投票数量，不计自赞、自评、自投，也不混入关注人数。不展示设备UUID。

下方五个标签：

| 标签 | 内容与操作 |
|---|---|
| 生成历史 | 本设备试穿任务，按时间倒序；显示真实状态/时间，成功才展示结果图，失败不展示原服饰图冒充结果；可回到服饰详情查询或删除任务。顶部分类“全部/处理中/已完成/未成功”。读取列表本身不向供应商轮询。 |
| 收藏 | 本人收藏的社区帖子；点击进入现有帖子详情，可取消收藏；原帖删除后收藏随之移除。 |
| 发布 | 本人显式发布的四类社区帖子；点击现有详情，复用删帖/赞/评论/投票。 |
| OOTD | 默认私密的每日穿搭记录，按穿搭日期倒序；新增、查看、编辑日期/备注、删除。相同日期允许多条记录，不悄悄覆盖。 |
| 搭配 | 已持久化且仍有衣物引用的个人outfit_sets；显示衣物缩略图、温度/场合、理由及原降级标识，可选为OOTD。旧方案没有生成时间字段，显示“生成时间未记录”，不从ID、文件时间或排序推算。缺件/失败会话没有可展示方案时，不制造空方案卡。 |

收藏按钮补在社区帖子详情，独立于点赞；收藏状态仅本人可见。内容采用游标分页（每次20），切标签取消请求，错误可原位重试；不会全量拉所有社区帖子后在浏览器做本人过滤。

从首页“我的档案/身材档案”仍直达原档案页；从底栏“我的”进入新个人中心。个人中心子页与浏览器返回保持对应，返回恢复原标签/滚动位置；底栏维持首页/衣橱/社区/我的。

### 积分明细

顶部说明“每日首次访问+10”，显示服务器返回余额与真实流水；没有记录时显示空态，不预填50分。应用启动、重新获焦/恢复前台及导航时经过前端节流调用签到POST，保证常开页面跨日后再次访问也可领取；失败不阻止衣柜/社区使用，积分页可重试。前端节流只减少请求，不决定资格；页面重载、React重复effect或多标签同时访问均不得重复加分。

采用北京时间Asia/Shanghai，以取得SQLite写锁后的日期为准。余额由流水求和，不另维护可能漂移的余额列；POST返回新增与否、当天日期和余额。GET只读，不加分。重放旧日参数无效：客户端不得提交day、分值或余额。

积分仅作测试版访问记录，不是付费资产，也不改变原识别/编排/试穿配额。邀请奖励、分享得分按钮不展示，避免暗示不存在的发奖能力。

### 收到的互动

标题和参考图相同；新设备为空态。读取别人对本人帖子的点赞/评论，以及关注事件；投票按帖子聚合为“当前收到N票”，不称为未读新增、不暴露投票者与其选项。点击关联帖子进入现有详情，关注项可查看作者公开帖子。

第一版展示仍存在的互动，不建立不可删除的通知副本：取消点赞、删除评论/帖子或撤销关注后相应项消失。不存在历史未读系统，因此不显示虚假未读角标，也不承诺推送/私信。列表时间来自真实记录，按时间/id稳定分页。

### 设置

浅灰蓝背景、白色圆角分组、右箭头、固定顶部返回，长页面可纵向滚动。

| 分组 | 可用项目 |
|---|---|
| 身份 | “当前设备身份”解释本机保存与不可找回；编辑头像和昵称。没有账号绑定/更换手机号/退出登录按钮。 |
| 帮助 | 项目主页、常见问题、反馈或投诉。反馈提交到本地服务端真实保存，成功文案为“反馈已保存到测试服务”，不声称有人已接收或承诺处理时限。 |
| 数据与隐私 | 测试版使用说明、数据处理说明、隐私设置、个人信息采集清单、个人信息共享清单；按实际代码说明设备标识/身材/图片/社区副本/模型服务处理，区分默认私密与主动发布。 |
| 关于 | 当前版本读取现有package.json版本0.1.0（构建时静态导入），不复制参考图v1.1.16或备案号。 |
| 数据管理 | “清空本设备全部数据”，使用已有清空接口并扩展新表和文件；二次确认及删除中禁用，成功刷新个人中心，失败保留当前页面。 |

隐私设置提供有实际效果的操作：查看本设备数据范围、进入本人公开帖子管理、清除头像/清空数据。首版不放尚未接通行为的“个性化推荐”“风格推荐”开关，不修改原推荐算法或prompt。说明页面是测试产品事实说明，不冒用竞品法律文本或声称正式备案。

### OOTD 编辑

用户先选日期（默认北京时间今天，可改历史日期）和两种来源之一：

- 上传一张本人/获许可穿搭照片：JPG/PNG/WebP，单图≤10MB，经现有图片内容校验，本地保存；不做识别或试穿，不上传供应商。
- 选择本设备已生成搭配：展示可选方案，保存set引用；不复制衣柜照片或生成新推荐，不能选别人的set。

标题≤80字、备注≤500字；可留空标题，界面显示“日期·今日穿搭”。编辑首版仅改日期/标题/备注，改变来源需另建记录，明确提示。创建凭据由后端签发，前端同一尝试复用；同草稿同内容返回原记录，不同内容409；断网后保留图片/输入并可重试，不重复建档。删除记录后重放旧凭据410，不重新写回照片。

OOTD照片不对社区公开。若未来要分享，需要独立显式发布流程，本轮不自动复制。衣物删除继续执行D10-c：引用型OOTD读取当前剩余方案；空方案删除后set引用置空、记录显示“原方案已删除”，不从快照复活已删衣服或照片。删除OOTD不删除原衣柜/原方案。

## 数据结构与隔离

新增009迁移，只CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS；不改旧表、不删列、不DROP；init_db现有扫描器自动执行。所有私有记录owner非空，服务端只从X-Device-ID依赖取owner，不信任body/query中的归属字段。任意ID访问与写入强制匹配owner，跨设备404。公共帖子仍仅返回既有白名单字段，不返回私人资料。

| 新表 | 核心字段与约束 |
|---|---|
| personal_settings | owner_id PK；nickname、avatar_path（可空）、avatar_version、created_at、sources。昵称1–24字，trim后不能为空，无HTML渲染。 |
| point_entries | id、owner_id、day、delta固定10、reason固定daily_visit、created_at、sources；UNIQUE(owner_id,day,reason)。只存真实获奖流水，不允许客户端分值。 |
| point_daily_claims | owner_hash、day、expires_at、sources（派生来源，无私人内容）；PK(owner_hash,day)，加盐哈希沿用quota_key；不存原设备UUID。清空后防同日重领，次日0点可删。 |
| personal_favorites | owner_id、post_id FK社区帖子ON DELETE CASCADE、created_at、sources；PK(owner_id,post_id)。私人收藏列表不向作者公开。 |
| personal_ootds | id、owner_id、client_id、request_hash、worn_on、title、note、kind(photo/outfit)、photo_path或set_id、created_at、updated_at、sources；UNIQUE(owner_id,client_id)。set_id FK ON DELETE SET NULL；触发器验证非空set属于同一owner，允许源方案删除后空引用。 |
| personal_feedback | id、owner_id、client_id、request_hash、category(feedback/complaint)、text(1–1000字)、created_at、sources；UNIQUE(owner_id,client_id)，不收手机号/邮箱。 |
| personal_write_receipts | token_hash、owner_hash、purpose、day、expires_at、state(issued/consumed/revoked)、payload_hash（可空）、sources；token_hash PK。只留签发凭据与内容的加盐摘要，不存原设备UUID、图片或文本。一般写入凭据次日0点清理；purpose=clear是服务端内部操作标记，恢复确认并完成文件清理后删除，不向客户端签发。 |

全部新增实体/输入/响应模型放app/models.py；旧模型与cases字段结构不变，不改冻结cases来填新功能。请求schema extra=forbid，日期、字符串、分页限额严格校验；外部响应只返回需要的字段，不含文件路径。头像和OOTD照片放现有uploads/<owner>/personal/下，采用不可猜ID/版本路径并验证resolve后的目录归属。头像≤2MB，替换后只删旧头像，不能误删衣柜共用文件；图片读取带设备头、no-store、nosniff。原子文件替换/事务失败补偿，不遗留半条可见记录或可访问孤儿照片。

## 积分与清空语义

签到在owner_lock和BEGIN IMMEDIATE内处理；取写锁后决定当日。清理过期匿名领取标记，用(owner_hash,day)唯一约束领取；新领取与+10流水同事务完成。并发只产生一条流水。若匿名标记已存在但个人流水已被清空，则当天返回未新增、余额0，不补发。没有永久设备领取记录。

清空本设备数据：同现有锁和事务撤回本人公开帖子/互动、删衣柜/身材/试穿，再清理设置/头像、积分流水、收藏、OOTD及照片、反馈。新文件只在uploads本设备子目录内删除；事务/文件处理失败须返回中文并遵守现有社区照片补偿流程，不复活删除中任务。保留设备ID、原当日匿名AI配额及当日积分领取标记至次日0点；其他设备及体验目录不动。确认弹窗说明“积分余额和记录一并删除，今天已领取的积分不会补发”。

清空文件采用先校验路径、再rename暂存的顺序：在同owner_lock内，将整个uploads/<owner>/私有目录（含衣柜/人像/头像/OOTD）移至该owner专用的不可通过API访问暂存目录；社区公开副本沿用stage_owner_posts。然后提交DB清理，事务回滚恢复两个暂存区；提交成功才purge。清空后文件purge失败返回“数据已清空，照片清理未完成，请重试”，重试应继续清理暂存，不回滚或重建业务记录。不得在DB提交前直接unlink/rmtree私有目录。启动/重试只清理已确认提交的暂存，不以目录存在与否猜测事务结果。

进程崩溃恢复的提交判据预留在A协议/第7表：持owner_lock先独立持久化purpose=clear、state=issued的操作标记；暂存目录和本地路径清单关联同一随机nonce。业务清空事务内将该标记改为consumed（不把自身作为普通凭据撤销）。启动/重试先取得对应owner锁：issued表示事务未提交，依清单restore；consumed表示已提交，继续purge。处理可重复，恢复/清理完成才删除操作标记；一般日界过期任务不删未恢复的clear标记。路径清单只在本地暂存区，不通过接口/日志返回。B段在main启动检查与清空重试中接入，不新增顶层目录或依赖。

为避免删除/清空后旧请求重建内容，新增写入凭据：POST /api/me/write-tickets?purpose=ootd|feedback|avatar|settings|favorite，服务端生成nonce、绑定owner_hash和purpose、HMAC签名，15分钟有效且不过午夜，并注册匿名issued行。所有新个人中心写入使用同一尝试的ticket；服务端取得owner_lock与写锁后重新校验到期、purpose和状态，再读取/写入照片，完成与consumed状态/请求摘要同事务。重复同内容不重复写；内容变化409。OOTD/反馈活记录已删除则旧consumed ticket返回410；其余修改旧consumed ticket只返回当前状态，不重放修改。清空将该owner全部issued/consumed凭据置revoked，保留匿名标记至次日0点；旧在途请求和重放都返回410。凭据失效后前端保留输入，只有用户明确重新提交才签发新的尝试，禁止自动换ticket复活内容。

匿名point_daily_claims和personal_write_receipts中的一般写入凭据随现有日界清理任务过期，不能仅靠下次访问惰性清理；A段扩展expire_quotas，并用新测试覆盖，不改变原配额格式或保留周期。内部clear标记按上述恢复规则清理。流水、设置等个人数据仍正常保留至用户清空，不与匿名日界标记混淆。

## 接口草案

统一新增/api/me；除现有公共帖子响应外，下面接口全部私有，必须设备头。列表limit≤20，游标绑定列表类型/筛选、日期/id键，不接受任意SQL。

- GET /api/me：昵称/是否有头像/版本、关注/粉丝/当前互动计数；只读不创建或签到。
- POST /api/me/points/check-in；GET /api/me/points（余额+分页流水）。
- POST /api/me/write-tickets?purpose：上述短期写入凭据，不扣积分、不触发模型；归属/签名/过期规则见上节。
- PATCH /api/me/settings（昵称）；PUT/GET/DELETE /api/me/avatar（上传、读取、移除）。改昵称同步既有community_authors；尚未创建作者时，后续社区作者创建从设置读取昵称，身份ID不变。
- GET /api/me/content?tab=history|favorites|published|outfits：分类型返回，不混淆数据；history可按任务状态筛选。GET /api/me/outfits/{id}返回当前仍存在的衣物和真实原理由，跨owner404。
- GET /api/me/people?tab=following|followers；GET /api/me/authors/{public_author_id}/posts：只读公开帖子，不查私人衣柜。
- GET /api/me/interactions：上述收到的互动分页；不生成推送或私信。
- GET /api/me/favorites/{post_id}；PUT/DELETE同路径：收藏状态及幂等写入；帖子不存在404，重复取消可204。
- POST /api/me/feedback：前端client_id幂等；不自动向GitHub/邮件/飞书发送。
- 独立router实现GET/POST /api/me/ootds；GET/PATCH/DELETE /api/me/ootds/{id}；GET /api/me/ootds/{id}/photo。新增使用multipart metadata+可选photo，二选一来源；日期编辑为JSON。删除重复404，照片随记录删除。
- 清空复用DELETE /api/wardrobe/items，不新增“注销账号”伪语义。

个人中心历史列表直接读本地tryon_jobs，不调用tryon.get或其他供应商查询；历史卡携带product_id和明确task_id，ProductDetail增加可选initialTaskId，指定时查该任务，不再自动取recentTryons()[0]覆盖。首页旧入口仍默认最近任务；指定任务被删除/跨owner时显示404中文提示，不悄悄切换别的任务。用户主动进入原试穿详情后仍按T21节流/预算处理。所有失败返回中文且保留可重试输入，前端切页取消请求并检查设备ID漂移；图片ObjectURL在换图/卸载/失败及时释放。

## 实施顺序与文件范围（本次申请一次批准后连续执行）

先单独提交AGENTS.md §2限定例外：只允许T22设备每日+10和余额/流水，不开放邀请奖励、充值、兑换、会员付费或改AI配额。随后单独提交docs/decisions.md新D15（本设计中的私密、清空、日界和来源删除语义）。不混入产品代码。

每段全量make test与make lint通过再进下一段。只改下列批准文件，新增需求/超范围修改先记录backlog并重新确认；文档、CHANGELOG、新报告与验收截图另计。阶段重复列出的文件可在该段继续完善。

| 段 | 内容 | 代码/配置/数据文件 |
|---|---|---|
| A（8） | 完整新增协议/迁移、签到与积分读接口、日界清理 | app/models.py；app/migrations/009_personal_center.sql；app/db.py；app/services/personal.py；app/routers/personal.py；app/main.py；app/tests/test_personal_api.py；app/tests/test_db.py |
| B（7） | 私密OOTD与照片、扩展全量清空 | app/services/ootd.py；app/routers/ootd.py；app/main.py；app/routers/wardrobe.py；app/services/personal.py；app/tests/test_ootd_api.py；app/tests/test_personal_clear.py |
| C（7） | 本人内容/社交统计/收到互动/收藏/设置头像昵称与反馈接口 | app/services/personal.py；app/routers/personal.py；app/services/community.py；app/tests/test_personal_api.py；app/tests/test_personal_content.py；app/tests/test_personal_media.py；app/tests/test_personal_interactions.py |
| D（8） | 前端统一API/照片组件、个人中心入口、保留首页直达档案 | web/src/lib/personalApi.ts；web/src/lib/personalApi.test.ts；web/src/pages/My.tsx；web/src/components/PersonalPhoto.tsx；web/src/App.tsx；web/src/components/BottomNav.tsx；web/src/pages/Home.tsx；web/src/components/AppIcon.tsx |
| E（8） | 积分/消息/设置/OOTD编辑及内容详情、完整视觉样式 | web/src/pages/Points.tsx；web/src/pages/Messages.tsx；web/src/pages/Settings.tsx；web/src/components/PersonalContent.tsx；web/src/pages/OotdEditor.tsx；web/src/pages/My.tsx；web/src/lib/personalView.ts；web/src/styles.css |
| F（8） | 社区详情收藏/指定任务历史接线、前端状态测试与联调修正 | web/src/pages/PostDetail.tsx；web/src/pages/ProductDetail.tsx；web/src/lib/personalView.test.ts；web/src/pages/My.tsx；web/src/pages/OotdEditor.tsx；web/src/pages/Settings.tsx；web/src/components/PersonalContent.tsx；web/src/styles.css |

模型/schema与响应解析测试在A/D先覆盖完整协议，E/F验证前端状态转换。旧测试断言不删、不skip、不放宽。已发现test_db.py逐表严格等值：A段只新增7个模型import及expected字典中的7个新表条目，保留旧条目、全部原assert和旧表字段检查，借此把同等严格的schema检查扩展至新表，不用忽略表或删断言绕过。其他未预料的硬编码依赖先报告，不顺手修改。

## 验收

1. A每设备首访10、同日重放/多线程并发仍10、北京时间跨日20、GET不加分；写锁等待跨日按锁后日期，客户端不能指定积分/日期。迁移重复执行不重复灌数据，旧衣柜/方案原样保留，日界清理只删除过期匿名标记。
2. 双设备真实HTTP验证：A/B积分、头像、收藏、OOTD/照片、本人生成历史隔离；拿A的ID由B访问404；任何响应没有原UUID/路径泄漏到公共作者/帖子。历史读取不触发供应商调用。
3. 收藏添加/重复添加/取消/刷新；A收藏B公开帖子，B删帖后A收藏列表消失。昵称修改后旧帖与后续新帖均展示真实昵称，头像不自动公开。
4. A发布、B赞/评/关注/投票，A收到真实互动；A自己的动作不计收到互动，取消/删除后对应消息消失；投票只聚合、不暴露B的选项。关注/粉丝列表计数和内容一致，分页不重复。
5. OOTD照片和自有方案分别创建、刷新恢复、历史日期/同日多条、编辑、删除；重复client_id不重复记录、内容冲突409；跨owner set拒绝；删衣后只显示剩余衣物，空set删除后显示源已删除；删OOTD不删衣柜/原方案。
6. 清空A后头像/积分流水/收藏/OOTD/反馈和原私有数据删除，公开帖子撤回；B和目录不变、A当日匿名积分标记与原AI配额保留，当天重试不补领，次日可领。检查照片不遗留；删除OOTD后旧POST410，清空后旧凭据及在途写入410、照片不复活；文件暂存失败/DB回滚可恢复旧照片，提交后purge失败可重试清理、不重建记录。历史两个同商品任务逐一点开显示所点task_id，删除旧任务后不自动显示新任务。
7. 375×812实际检查我的首页五标签、档案、积分、互动、设置上下半、OOTD新增与详情、帖子收藏；loading/empty/error及图片失败降级均截图，scrollWidth≤375。无真实试穿数据时使用明确标注的隔离测试注入验视觉，不把注入截图说成真人生成效果。
8. 每段全量make test/make lint，最终cd web && npm run build；保留真实输出。134冻结项SHA256不变；不改prompt/cases、LLM日志规则、不加依赖、不部署/开隧道、不自动同步GitHub或上传本地求职材料。

报告更新tasks状态/实测证据和CHANGELOG；区分实现、离线注入与真实双设备交互。回滚使用功能前备份恢复数据库及uploads，停服后操作；009没有DROP/DOWN脚本，不靠删除新表伪装回滚。实施前记下备份命令和位置（不提交运行数据），本轮不实际回滚用户资料。

## 设计审查记录

2026-11-20完成只读独立builder check及复审，三项审批前问题均已补齐：删除后凭据重放不复活、历史按task_id打开、清空私有照片暂存与事务补偿；再补持久化clear标记应对rename后进程退出。复审结论无剩余审批阻塞。未运行功能测试或真实调用，功能仍待完整设计/文件范围批准后实施。

实施裁决：指定历史任务最终采用只读本地快照接口，历史详情不自动查询供应商。原服饰试穿入口的查询/预算逻辑保留。
