# T20 · 真实社区与导航合并设计

日期：2026-11-18。状态：真实社区及AGENTS限定例外已获人类批准，分段文件范围待批准；未写产品代码。

## 意图与参考图

用户要求将搭配与衣橱底栏合并，增加社区：关注/全部/搭配/投票四个栏目、普通帖子详情、发布入口和投票详情。明确选择不同测试者可以真正看到彼此发布并关注、点赞、评论、投票，禁止假数据冒充真实社区。

收到6张参考图，按实际界面识别：图1全部图文信息流、图2搭配信息流、图3关注空态、图4投票信息流、图5发布类型弹层、图6买不买投票详情。没有第7张或普通帖子详情独立截图；后者以图6的作者/大图/正文/底部互动结构去掉投票区实现。仍采用当前粉色风格，不使用截图中的人物/账号/点赞数或Lookie品牌作为真实数据。

## 架构选择

沿用现有React/FastAPI/SQLite/本地文件、设备UUID身份，不增加注册登录、云数据库、对象存储、SDK或AI能力。社区数据与私人衣柜分表。另一种单机模拟不符合已确认多人可见目标；账号系统/外部社区平台会扩展现阶段身份与部署范围，因此不采用。

每个设备在首次社区写操作时建立独立公开作者ID及自动昵称“衣友xxxxxx”；公开ID随机生成，不能从中反推出设备UUID。无需实名/头像，也不新增昵称编辑页面。设备标识仍只由既有deviceId.ts管理。社区身份仅代表设备，不宣称是跨设备登录账号；同一后台数据库中的测试者可相互看到帖子，刷新列表可见最新内容，不做实时推送。

本轮只做社区功能，不自动部署、开启隧道或同步GitHub。外部测试仍需连接同一个服务，不能把两个各自本地数据库视为同一社区。

## 导航与页面

- 底部：首页/衣橱/社区/我的。衣橱内部显示“我的衣橱 / AI搭配”切换，保留原生成页、天气温度预填、所有上传/确认/编辑/删除功能；搭配子页在底栏归属衣橱。
- 社区首屏：粉色顶部+白色圆角内容区，关注/全部/搭配/投票栏目、右上相机图标，双列不等高卡片。真实计数，作者昵称和赞数；不显示未定义的火热度、积分+3、试穿按钮。
- 关注：只显示我关注作者的帖子，无关注或无帖子时按图3做空态，引导到全部找作者；不能填假关注。
- 全部：所有显式发布的社区帖子（包括自己），按创建时间倒序。
- 搭配：仅搭配分享（选自己衣物生成图片拼排的帖子），不是私人推荐列表。
- 投票：穿搭投票/买不买两类帖子。卡片点进详情展示选项和真实票数。
- 普通详情：顶部返回/作者/关注，大图或图片组、标题/正文/日期、评论列表、输入评论、赞与评论数；自己的帖子提供删除确认。没有投票区和虚拟试穿。浏览器后退/返回恢复原栏目。
- 相机：打开图5式发布类型选择与预览弹层，再进入编辑页。四类见下表。没有奖励积分或默认勾选公开私人衣柜。
- 发布页：选择图片/衣物、标题/正文或投票问题、预览、“发布到社区”按钮。显示“发布后其他使用者可查看选中的图片和文字”；用户确认发布才提交。发布中禁用重复点击，失败保留File/选择/文本/draft_id，可原地重试；取消明确结束当前草稿。
- 投票详情：普通详情结构+选项按钮，买不买为“不值得/值得”PK；穿搭投票为2至4个图片选项。提交后显示票数/百分比和本人选择，不能改票。没有截止时间或投票奖励机制。

| 类型 | 输入 | 栏目归属 |
|---|---|---|
| 穿搭分享 photo | 1至9张主动选取照片、标题、正文 | 全部/关注 |
| 搭配分享 outfit | 从自己的衣柜选2至8件有照片的衣物，确认公开所选图片副本；标题/正文 | 全部/关注/搭配 |
| 穿搭投票 poll | 一个问题、2至4个带图片和名称的选项 | 全部/关注/投票 |
| 买不买 buy | 一个问题、1张图片，固定不值得/值得两选项 | 全部/关注/投票 |

图片只支持JPG/PNG/WebP（检查内容及MIME），单图≤10MB、每帖总计≤30MB。标题≤80字符、正文≤2000字符；发布不能只有空白。评论1至500字符、纯文本渲染。表单长度、数量限制前后端一致，失败中文提示。

## 私人与公开边界

- 私人wardrobe_items/outfit_sets/outfit_items/sessions/body_profiles查询继续强制owner过滤，绝不把过滤改成可选参数。
- 只有社区公开表的帖子内容允许跨设备读取，仍要求有效X-Device-ID以支持当前用户互动状态。公开响应不包含任何owner_id、设备UUID、私有item_id、文件路径、身材资料、模型调用审计或照片SHA。
- 搭配分享只接受本设备的衣物ID；逐件检查owner和照片。发布时生成独立图片副本和允许公开的品类/子类/颜色摘要，不使用模型，不把整个WardrobeItem序列化公开。
- 已发布副本独立于私人衣物：删除衣柜单品不自动撤回帖子；发布页说明可通过删帖撤回，清空全部数据会撤回。
- 公开副本放在data/uploads/community/<公开作者ID>/<帖子ID>/，由独立社区照片接口提供，不能通过公共接口获取任意路径或私人衣柜照片。图片URL仍经前端API带设备头取blob，ObjectURL及时释放。
- 作者可删自己的帖子/评论，删除他人内容404；点赞/关注/投票只作用于公开存在的帖子/作者，禁止关注自己。昵称是独立设备公开代号，不复用真实头像或用户资料。
- DELETE /api/wardrobe/items既有“清空全部”语义保持：同owner锁内撤回自己的社区帖子及图片、删除本人评论/点赞/投票/关注、清理社区作者身份，再清理原业务数据；他人无关帖子保留。保留当日匿名额度，原响应计数字段及旧断言不变。

## 数据协议（models.py唯一来源）

新增007迁移，8张社区表，均附sources JSON，字段来源在对应Pydantic字段元数据标user/derived；不引入LLM model来源。用户文字/照片/选择为user，ID/作者关联/时间/计数/快照复制为derived。

| 表 | 核心字段与约束 |
|---|---|
| community_authors | id公开随机ID主键；owner_id非NULL唯一且只在服务端使用；nickname、created_at、sources |
| community_posts | id主键、author_id外键、kind(photo/outfit/poll/buy)、title/body、created_at、draft_id、request_hash、sources；UNIQUE(author_id,draft_id) |
| community_media | id主键、post_id外键、position、file_path、mime_type、caption、sources；UNIQUE(post_id,position)；path不出现在公开响应 |
| community_likes | post_id、author_id外键、created_at、sources；联合主键，PUT幂等 |
| community_follows | follower_id、followee_id外键、created_at、sources；联合主键，禁止相同ID |
| community_comments | id主键、post_id、author_id、text、client_id、created_at、sources；UNIQUE(author_id,client_id)防重试重复 |
| community_poll_options | id主键、post_id、position、label、media_id可空、sources；UNIQUE(post_id,position) |
| community_votes | post_id、author_id、option_id、created_at、sources；联合主键，复合外键确保选项属于该帖 |

仅新增表和索引，不删列不DROP，007重复执行幂等。外键开启，必要的ON DELETE CASCADE只用于删除用户明确撤回的社区数据。旧test_db精确表集合加入新表/完整字段检查，不降低旧表断言；历史迁移夹具保持历史结构。

新响应CommunityPostView仅有公开作者对象、类型/标题/正文/图片ID与摘要/时间、derived计数、当前用户liked/following/vote/can_delete。列表next_cursor分页，单页20项，上限20，稳定created_at/id游标；刷新首屏，前端按ID去重。

## 接口

所有API带设备头，参数使用Pydantic校验。参数错误400，非法媒体422/超大413，未找到或无删除权限404，冲突409；其他错误中文响应，不返回栈。

| method/path | 输入与行为 |
|---|---|
| GET /api/community/posts | tab=following/all/outfits/votes，cursor可选，limit≤20；返回posts/next_cursor |
| GET /api/community/posts/{id} | 公开详情/当前用户互动状态 |
| POST /api/community/posts | multipart：metadata JSON（draft_id、kind、title/body、item_ids或options）及photos；同draft同hash返回原帖，同draft不同内容409 |
| DELETE /api/community/posts/{id} | 本人删帖204，重复删404；删帖连带图片/评论/赞/投票，图片清理失败须报错且不能默默成功 |
| GET /api/community/posts/{id}/photos/{media_id} | 只读取该公开帖媒体，固定目录限制、MIME、nosniff，帖子删除后404 |
| PUT/DELETE /api/community/authors/{id}/follow | 幂等关注/取消；不能关注自己 |
| PUT/DELETE /api/community/posts/{id}/like | 幂等赞/取消 |
| GET /api/community/posts/{id}/comments | 分页公开评论，含本人可删标记 |
| POST /api/community/posts/{id}/comments | client_id UUID+text；重复同内容返回原评论，不同内容409 |
| DELETE /api/community/comments/{id} | 仅本人可删，其他404 |
| PUT /api/community/posts/{id}/vote | option_id；首次入库，同选项重试幂等200，不同选项409；返回真实票数和本人选择 |

所有互动计数由SQL COUNT计算，不在客户端伪加随机数；事务/联合唯一索引保证并发不重复。新增服务的SQLite写入事务保持短小；复制文件前做owner验证，失败回滚清理未发布文件。创建者与清空使用同owner_lock，删除与投票/评论冲突通过SQLite事务和外键处理。清空服务接收既有clear_items的同一connection，不在其BEGIN IMMEDIATE写锁内另开写连接。

## 分段文件范围（每段≤8，逐段全量验证与提交）

0. AGENTS例外已单独提交；设计批准后单独提交decisions新增D13，明确公开发布/隐私与导航边界。文档不计代码文件上限。

A 数据协议与迁移（4）：app/models.py、app/migrations/007_community.sql、app/tests/test_db.py、app/tests/test_community_db.py。

B 发帖/列表/照片/撤回及清空（6）：app/services/community.py、app/routers/community.py、app/main.py、app/tests/test_community_api.py、app/routers/wardrobe.py、app/tests/test_community_clear.py。

C 真实互动（3）：app/services/community.py、app/routers/community.py、app/tests/test_community_interactions.py。复用A的协议，不另加schema文件。

D 导航合并/社区信息流/图片API（8）：web/src/App.tsx、web/src/components/BottomNav.tsx、web/src/components/AppIcon.tsx、web/src/pages/Community.tsx、web/src/components/CommunityImage.tsx、web/src/lib/communityApi.ts、web/src/lib/communityApi.test.ts、web/src/styles.css。

E 详情与发布交互（≤7）：web/src/pages/Community.tsx、web/src/pages/PostDetail.tsx、web/src/pages/PostComposer.tsx、web/src/pages/Outfits.tsx、web/src/lib/communityApi.ts、web/src/lib/communityApi.test.ts、web/src/styles.css。

收尾文档与截图、独立审查修复：修改限已批准范围且每次≤8；若确需额外代码文件，先停下确认拆分。文档产物tasks/CHANGELOG/README/隐私政策/backlog/新设计计划/新报告另计。

## 验收

- 每段TDD；make test、make lint全绿后继续下一段，前端build通过；既有355后端/50前端测试不删不跳不放宽。迁移测试更新精确表集合，保留原字段/外键/幂等断言。
- 测试与浏览器使用临时库，不读取或清空真实衣柜。社区验收必须调用真实API/SQLite，不能用mock冒充跨用户数据；照片采用本地测试素材且标注验收夹具，不自动灌入用户实际社区。
- 设备A发布，B的私人衣柜仍为空但社区能看到A的公开帖子/照片；公开响应不含A的设备ID、私有item_id/路径/身材/审计。B不能删A；不能拿A的私有item_id发帖或通过社区照片路径取私图。
- B关注A→关注列表出现A；点赞/评论/投票真实入库，刷新结果与计数一致；重复PUT不重复计数、重复评论不增加，二选/多选均唯一；并发投票不超过一票/设备。
- 四类发布均可完成，失败后照片/文本/草稿ID保留，重试同draft只创建一帖；删除自己的帖子后照片404、互动清理。清空A后A的社区数据/图片及私人业务清空，B无关帖子保留，原当日匿名额度不被清空。
- 浏览器两独立设备上下文，375×812，无横向溢出、图失败有占位、ObjectURL释放；社区四栏目loading/empty/error、列表→详情→返回、相机→类型→编辑→发布、投票详情、评论/关注/点赞、导航合并后AI搭配入口均验。
- 独立whole-branch审查，一轮修复并回归；134冻结项SHA256不变，无新模型/真实天气调用、无新依赖。回填任务板/CHANGELOG，按既有授权no-ff合本地main；不自动发布GitHub/隧道。

## 边界与未做

不新增注册/登录/账号找回/跨设备身份同步、站外分享、商店导购、积分奖励、虚拟试穿、私信、推荐算法、运营内容搬运或自动内容生成。只有用户显式发布的副本对社区可见；新社区起始为空，不复制参考图的作者及数字。

## 设计审查与实现裁决

独立只读builder-check结论：没有必须再向人类确认的重大未决问题，A—E文件范围可成立。未联网、未写产品代码或读取真实data。

实现裁决：删除公开图片目录先在同文件系统移至不对外提供的uploads/community_trash/<owner UUID>/<postID>暂存区，再提交SQL删除；SQL失败则还原目录。提交后清理暂存区，若文件系统仍失败，返回明确“帖子已撤回，照片清理未完成，请重试”而不伪称完全成功；同owner重试删除可继续清理并204，其他设备仍404。清空全部同时清理该owner的暂存目录，保留当日匿名额度。该暂存区不是软删帖子表或恢复功能，也不得由照片接口访问。首次迁移前备份完整数据目录，回滚为停服务恢复备份并检出旧代码，禁止DROP回退。

设备身份不支持跨设备找回，清除浏览器本地设备标识会失去原身份管理权；这是沿用无注册阶段的限制，页面及验收说明明确，不把设备代号称为已登录账号。
