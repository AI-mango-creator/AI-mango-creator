# T21 首页服饰体验与真实AI试穿 · 设计草案

日期：2026-11-19。状态：用户已选择“先做试穿体验版，再接平台商品”；本设计、范围例外、资源和真实调用预算待确认，未写产品代码、未调用付费API。

## 目标与已确认事项

替换首页“我的衣橱灵感”列表和首页“上传衣物”快捷入口，采用参考图的粉色页面、服饰双列卡片、商品大图详情、试穿中状态。衣橱页的上传建档继续保留，已有AI搭配及社区不变。商品浏览和本人衣柜搭配是两条链路，体验服饰不进入wardrobe_items或filter_candidates，P2的衣柜外单品为0保持不变。

用户目前没有平台接口、合作授权或商品资料。已选择先体验版，因此展示“试穿体验 · 暂无平台合作”；只接纳确有使用权的图片。无图片时展示引导空态，不把参考截图当成授权商品源。标题/类别/来源按实际素材填写，无真实价格则省略价格，不编造品牌、销量、优惠或合作。购物车/购买按钮本轮不实现；以后有真实平台链接可另行接入。

## Approaches

1. 平台商品接口+试穿：商品可来自正式接口，需要平台应用、AppKey/签名及相应权限；当前用户没有相关资源，接入条件尚不具备。
2. 有使用权的体验素材目录+真实托管试穿：先验证视觉与试穿闭环，目录明确标注体验、不代表合作或成交价格；平台接入延后。**用户已选本路线**。
3. 纯视觉原型：能展示交互，不能证明真实试穿；与本次要真实能力的目标不符，不采用。

## 官方调研与服务建议（实现者建议，尚非人类指定）

- 淘宝官方商品详情API需要AppKey和签名；“不需要授权”不等于无需应用资格：https://developer.alibaba.com/docs/api.htm?apiId=46283 。本轮不接淘宝/拼多多/闲鱼，不抓取页面。
- 建议首版候选FASHN tryon-v1.6，直接使用现有httpx2调用官方REST，不引入SDK/新依赖。支持人物图+服饰图、tops/bottoms/one-pieces、异步任务，1 credit/成功结果图；美元充值金额、账号权限、网络可用性尚未验证，不引用搜索摘要作价格承诺。
- https://docs.fashn.ai/api-reference/tryon-v1-6
- https://docs.fashn.ai/api-overview/api-fundamentals
- https://docs.fashn.ai/api-overview/data-retention-privacy
- 阿里云旧试衣介绍和计费URL本次打开跳转至模型总览，暂不能据此保证现有DashScope账号可试衣；现有识别/编排配置不改。

真人图和服饰图采用data URI提交；return_base64=true取结果后落本地，不创建公开人像URL、不接OSS/CDN存储。供应商仍临时处理输入和结果；其文档说明base64结果可获取60分钟，请求元数据不会自动删除，不能宣称“本地清空会抹除供应商全部记录”。这些是官方政策，不是本账号已验证的行为。

## 用户流程与页面

- 首页保留档案、衣橱数量、天气、AI帮我搭、底栏。移除首页上传快捷按钮与个人衣物图墙；新目录顶部标“试穿体验”。衣橱仍可上传。
- 分类：全部/上装/下装/裙装，分别对应本服务支持的tops/bottoms/one-pieces；首版不假装支持鞋包首饰试穿。
- 卡片：素材图、真实填写的名称、类别、来源标签、“AI试穿”。点卡片进入详情，点试穿可进入同一详情的试穿操作。
- 详情：返回、素材大图/类别、体验来源，不显示虚构价格及商城购物车。按钮“AI试穿”；试穿前选择本人或获许可的人像照片，展示本地预览与向服务发送处理的说明，用户明确点击提交。
- 处理中：原商品图仍显示，“试穿中…”及真实状态文案，禁用重复提交。进度只报0/1和1/1，不编造百分比。允许离开页面，重新打开可查最近未完成任务。
- 成功：独立标注“AI试穿效果，仅作外观参考”，显示真实返回图，可切换原图/效果图；不宣称尺码、合身程度或布料还原保证，不自动公开到社区。
- 失败/配置缺失：中文提示；保留当前已选照片和商品，可原地处理/重试。没有key时显示服务未配置，不用合成假图顶替结果。
- 所有API页面有loading/empty/error；照片加载/解码失败文字占位；切页取消前端请求并释放ObjectURL。375×812无横向溢出，详情返回与浏览器前进后退明确。

## 数据与本地素材导入

新增迁移008（禁止DROP/删列）：

- experience_products：公开体验目录，固定owner_id='catalog'（不是NULL），id/title/category/image_path/source_label/rights_note/created_at/sources；只有本地开发者脚本导入。公开响应白名单不含文件路径、操作者信息。目录不含用户私人衣物，上传到衣柜不会自动进入目录。
- tryon_jobs：id/owner_id/request_id/request_hash/product_id/status/provider_task_id/portrait_path/result_path/error_kind/created_at/latency_ms/sources；UNIQUE(owner_id,request_id)，私有查询必须带owner。provider_task_id不返回前端。
- 实现采用独立tryon_daily_quotas表保存tryon计数与tryon_request_hashes匿名提交账本（JSON默认[]），以保持原daily_quotas五列写入兼容；不改原识别/编排20/30限额。详见实施计划Ruling。试穿限额拟为每设备3次/日、分享全站10次/日，等待人类确认；保留匿名owner_hash、清空后保留至次日0点与过期规则。

脚本scripts/import_tryon_catalog.py读取本地manifest和图片，必须有来源及使用权声明；默认dry-run，--apply才复制到data/uploads/catalog/<id>/并入库。同id同内容幂等，冲突响亮报错；不从远程任意URL抓图。素材不提交到公开GitHub，若要附公开展示素材须另核其授权。缺素材则自然空目录，不改既有cases/prompt/冻结文件来凑数据。

人物照片与结果仅在data/uploads/<owner>/tryon/保存，按owner提供图片。本人可删除试穿任务/照片，清空设备数据同时删除该owner试穿行及文件，保留目录与其他owner，保留当日额度。默认不将人像写入身材资料/社区，供应商的保留规则单独说明。

## 后端链路、预算与幂等

唯一模型出口仍为app/llm/client.py，新增试穿提交/查询函数；既有chat/vision和原日志字段不改。新试穿日志保持脱敏，记录任务/版本/耗时/状态，不记key、照片base64、完整输入或供应商原文错误。Pydantic模型集中models.py，所有供应商响应校验后使用。

拟新增：GET /api/tryons/ticket?product_id（签发短期提交凭据，无模型调用）；GET /api/experience/products、GET /api/experience/products/{id}、GET素材图；POST /api/tryons（product_id、photo、request_id、处理说明确认）、GET /api/tryons/{id}、GET /api/tryons?product_id（本设备最近任务）、GET结果图、DELETE任务。所有端点沿用设备头，跨owner任务/人像404。

供应商原生异步任务，无Redis/Celery/本地推理：POST先短事务保留本地request_id和额度，释放DB锁再提交；得到provider_task_id后保存并202。浏览器只查本地任务接口，由后端节流查询供应商，成功才落结果图；后续GET不重复生成。无浏览器时供应商可自行完成，下次本设备查询再取结果。

试穿是第三类能力，需要AGENTS/D7.1限定例外：每个用户任务只允许一次付费生成提交；每次HTTP超时≤20s，任务观察总时限拟120s，状态查询最多30次且最短间隔2s，非付费查询单独统计，不冒充“首调+重试2”。POST结果不明时不自动重发（供应商文档未承诺生成幂等），本地标记提交状态待核，提示可能已提交；不能用新request_id无提示地触发重复收费。明确拒绝/失败后，用户再次尝试需要新的任务确认并计额度。

同request_id同hash返回原任务；不同内容409。删除/清空不能抹掉已提交请求的拒绝凭据：每次首次保留时，同事务将加盐SHA256(owner+request_id)写入当日匿名额度账本；任务被删但账本命中时，旧POST返回410“此试穿已删除，请重新确认后创建新任务”，不再发生成、不恢复照片。账本不含原设备UUID、人像、结果或商品内容，与额度行一起次日0点删除。为避免日界后旧请求重放，POST还必须带服务端签发、绑定本设备/商品/request_id的HMAC ticket；有效期为15分钟且不跨当日0点，过期先拒绝再考虑任务创建，禁止自动换ticket重提。新ticket只能由用户重新确认试穿生成，与旧request_id不同。以上是实现者为避免重复收费作出的技术选择，不新增账号。并发提交只接纳一次，扣额、账本与本地保留必须同一SQLite事务；取得写锁后须重新校验ticket到期和归属日，防止等锁期间跨午夜；如供应商接单与本地写回之间中断，不自动重生成。清空/删除与在途写回通过owner_lock及存在性复查处理，不能复活已删任务或照片。启动后状态恢复仅查询已有provider_task_id，不重提无id任务。终止本地观察不宣称远端任务已取消/不会计费。

状态映射：未配置/401/403→服务未配置/不可用且无重试；429→限流提示、不自动再发生成；图像姿态/类型错误422、超时明确待查/稍后重试说明、供应商失败与解析错误中文，不返回500裸栈。试穿失败不走衣柜规则模板、不返回旧图冒充成功。

## 范围例外与分段文件草案（待批准后实施）

0. 先单独提交AGENTS限定例外（本任务体验目录/托管试穿、第三类能力及异步预算、原生图像API不适用max_tokens/temperature）；不放开爬虫/购物导流/分佣、本地推理或衣柜外推荐。再单独提交decisions D14与本任务预算，保留原决策历史。

A一次预先提供B所需完整协议、提交ticket签验及“匿名账本+扣额+本地任务保留”同事务接口，避免B回改models/db导致超范围。

A 数据/目录（7）：app/models.py；app/migrations/008_tryon.sql；app/db.py；app/tests/test_db.py（只扩展新增表/列的精确检查，不删原断言）；app/tests/test_tryon_db.py；scripts/import_tryon_catalog.py；app/tests/test_tryon_catalog.py。

B 原生试穿/接口/清空（8）：app/llm/client.py；.env.example（新增占位，不填真实key）；app/services/tryon.py；app/routers/tryon.py；app/main.py；app/routers/wardrobe.py；app/tests/test_tryon_api.py；app/tests/test_tryon.py。

C 首页/详情/结果（8）：web/src/pages/Home.tsx；web/src/pages/ProductDetail.tsx；web/src/components/ExperiencePhoto.tsx；web/src/lib/tryonApi.ts；web/src/lib/tryonApi.test.ts；web/src/lib/tryonView.ts；web/src/lib/tryonView.test.ts；web/src/styles.css。详情作为首页子视图，底栏归首页，无需新增顶层路由或改底栏。

收尾审查修复只在已批准范围，每次≤8；否则先重新确认。文档：tasks/CHANGELOG/README/隐私说明/新报告与设计计划另计。每段全量make test、make lint后继续；不安装新依赖、不改cases/prompt/134冻结证据；每段提交，最后按已有授权no-ff合main，不自动同步GitHub或开启隧道。

## 验收

- 离线测试注入供应商任务响应，仅用于测试；默认运行路径直连真实client，不能有USE_MOCK生产开关。
- 导入素材使用权必填、dry-run不写、幂等；衣柜与体验目录完全分开；迁移重复执行不重复灌入，不变更旧业务数据。
- 设备隔离、每日额度并发边界、同request_id不重复生成/扣额、提交超时不自动重发、状态恢复不重提、清空在途回包不能复活数据；删任务/清空后重放旧POST为410且供应商调用不增加；午夜账本清除后旧ticket仍因过期被拒绝；同设备清空后额度仍保留。
- API key/任务ID私有、图片不公开、响应只走白名单、日志无key/base64；用户确认处理说明前不调用供应商。
- 单元测试失败注入覆盖未配置/401/429/提交超时/解析异常/姿态失败/成功；真人测试不得拿注入结果冒充。
- 375×812真实接口截图：首页空/载入/错误/卡片、商品详情、选人像/提交说明、试穿中/成功/失败保留；ObjectURL释放；衣橱/社区/原搭配回归。
- 首轮真实验收拟3组有权使用的服饰+人像，最多3次生成提交（至多3 credits，需人类确认金额/充值与权限）。逐条记录真实耗时、结果、实际credits；不预估准确率、通过率或速度，不能把供应商典型时长写成项目实测。无key/素材时状态保持🟡“待真实试穿验证”。

## 尚需人类提供/决定

- 是否采用FASHN、是否具备/愿意开通其API账号，人民币/美元预算上限及首轮3次提交额度。密钥仅在本机.env配置，不在聊天里发送；在确认前不注册/充值/发送人物图。
- 至少一组有使用权的服饰参考图及本人/获许可人像，能否用于本机真实验收；公开截图另需许可，默认不把真人原图/结果提交GitHub。
- 本设计、限定例外及A7/B8/C8是否批准连续实施。无素材先保持空态，资源未就绪仍可做已批准的离线代码，不宣称完整体验已验收。


## 独立设计审查（2026-11-19）

只读审查发现“删除任务后去重证据消失，可重复收费”的矛盾，已在草案中补匿名当日提交账本+短期HMAC ticket、410拒重与午夜边界验收。A预先提供B所需完整协议/事务接口；A7/B8/C8可成立。账号、预算、素材与正式范围批准仍需人类确认；不把这些未知资源当成已具备。

复审结论：上述机制已解决重大矛盾，无其他阻碍规划的重大问题；正式实现仍须遵守写锁后重新核验日界与到期时间。
