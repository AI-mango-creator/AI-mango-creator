# 算法衣橱 · Wardrobe Copilot

面向出门前需要从已有衣柜中快速选衣的通勤人群，输入衣柜照片、温度和场合，输出可执行搭配、属性理由与缺件提示。当前是P0验证原型，开发时间2026.11至今，未整体结项：照片上传→识别入库→用户确认→真实编排已接通，支持单品删除和方案图片预览；换一套交互待完成。

**评审先看：[作品说明](docs/作品说明.md)**，包含作品信息、本人负责内容与Codex辅助方式、界面截图、产品取舍、代表case及验收结论；[简历短版与面试口述](docs/05-简历文案.md)另列。现可用`make share`生成临时HTTPS测试链接，见[临时测试指南](docs/10-临时测试指南.md)；长期线上地址和完整演示视频仍未提供，下面的localhost地址只用于本地运行。

## 发链接给朋友测试

在本机终端执行`make share`，等待输出“测试链接已连通”，复制HTTPS链接给朋友；上传衣物后先逐件确认，再输入温度/场合生成搭配。电脑与分享进程须保持运行，前台Ctrl-C停止。需要退出终端后继续分享时，改用`.venv/bin/python -m scripts.share --background`启动，`--status`查询验证最新地址，`--stop`停止；免费地址轮换后需重新发链接，旧链接不会跳转。使用独立测试库，全站每天最多识别20张/生成30次，不导入原衣柜；API调用仍使用真实模型并消耗额度。免费通道较慢，照片超时会退为文字占位。实际三张上传、确认、一次真实生成及双设备隔离记录见[T16报告](docs/reports/t16-share.md)。

## 30 秒跑起来

前提：已安装Python 3.11、Node 22 LTS，仓库依赖已就绪，`.env`已填写有效API配置。在仓库根目录执行：

```bash
make seed
make dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。`make dev`同时启动后端8000、前端5173，Ctrl-C一起退出；前端通过Vite代理访问`/api`。`make seed`幂等灌入legacy隔离区，普通设备不可见；新设备衣柜为空，不会自动收到测试衣物。需演示基准衣柜时，仅在本地显式用下文`seed --owner-id`。

先看“我的衣柜”，可选择/拖入衣物照片自动建档，失败保留照片并原地重试；可编辑品类、子类、颜色、材质、图案；切到“今天怎么穿”，以18℃、通勤生成方案。上传后每件先待确认，点“这是对的”或编辑五字段保存后再参与搭配；confidence仅辅助。新设备先建档确认再生成；请求统一携带设备UUID，编排实际调用模型。授权、限流、超时或解析错误进入规则降级时显示基础搭配黄条；其他失败显示中文错误提示；候选不足显示缺件卡。

卡片右上角可删除单品，二次确认后硬删除历史引用并清理空方案；共用照片最后一件引用删除后才清理，失败保留卡片。方案按上装/下装/鞋展示缩略图，冷天外套继续显示；图片加载或解码失败转品类·子类文字块，原理由保留。[T15截图及验收边界](docs/reports/t15-experience.md)有完整说明。

### 身材资料与衣橱分类

“身材资料”页可填写身高（cm）、体重（kg），从X/A/T-Y/H/O五种带示意图的体型中选择；可留空或清除。资料按设备保存，只供搭配理由参考，不作为硬性筛选或合身保证。

衣橱支持全部、上装、下装、裙装、套装、鞋子、包包、首饰、配饰、未分类十个入口。外套归上装，半身裙与连衣裙归裙装；未分类须选择归属并填写具体品类名称，上装/裙装另明确搭配位置。套装、包包、首饰本轮仅收纳，不新增推荐槽位。资料与分类的[测试及手机截图](docs/reports/t18-profile-categories.md)已记录；新识别v3和带资料编排v2尚未做真实模型复测。

### 首次准备

首次准备需要uv；已有`.venv`和`web/node_modules`时保留现状。仅在缺失时准备，Python依赖使用锁定版本：

```bash
test -x .venv/bin/python || uv venv --python 3.11 --seed .venv
make setup
test -d web/node_modules || (cd web && npm ci)
cp -n .env.example .env
```

编辑`.env`，填写`DASHSCOPE_API_KEY`、账户对应的OpenAI兼容`DASHSCOPE_BASE_URL`及`DASHSCOPE_MODEL`。已验证文本模型为`qwen3.8-flash`；识别使用`qwen3.8-omni-flash`。密钥只由后端读取，不进入前端。

健康检查与单次真实生成：

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/api/outfits \
  -H 'X-Device-ID: <设备UUID>' \
  -H 'content-type: application/json' \
  -d '{"temp_c":18,"occasion":"commute"}'
```

将`<设备UUID>`替换为浏览器Network请求头中的X-Device-ID；设备ID只由deviceId.ts管理，组件不直接读localStorage。照片请求也带设备头，前端以blob显示。健康响应为`{"status":"ok"}`。生成响应含方案或结构化缺件、`latency_ms`、`degraded`、`degrade_reason`、`prompt_version`；真实模型调用会消耗API额度。

## 实测结果与口径

用例集29条：R识别9条、B组合10条、C边界/注入5条、A素材未备5条。A单独列跳过，不计可跑24例；规则来自同一份[cases.json](cases/cases.json)。

| 证据 | 结果 | 如何理解 |
|---|---|---|
| [官方单次v1](docs/reports/eval_v1.md) / [v2](docs/reports/eval_v2.md) | 各20/24，N=1 | 冻结的单次基线，无逐轮提升结论 |
| [v3组合重复采样](docs/reports/eval_v3.md) | B累计21/30，N=3 | 每例报通过次数/3；B03/B05/B10各0/3，其余七例各3/3 |
| v3识别与边界 | R8/9；C5/5 | R只读既有v2单次录制；C为单次纯规则或客户端层注入 |
| [识别repeatability](docs/reports/t11-repeatability.md) | R02/R03各2/3，各n=3 | 小样本观测；R03单次转绿不足以证明稳定修复 |
| v3生成链路耗时 | 4178–14054ms，n=30 | 2026-11-13 16:29:33–16:33:33，+08:00，含重试；不是HTTP端到端P95统计 |
| v3最终方案 | 90套，衣柜外ID=0 | 32次客户端尝试，30个生成场景最终均未降级 |
| [T5-D2历史上传到卡片](docs/reports/t5d-upload-chain.md) | 9/9；5411–8880ms，n=9 | 当时选图→模型→入库→卡片；T13已新增逐件确认，含确认耗时未另测，不用旧值代表当前完整建档 |
| [T13隔离与确认](docs/reports/t13-data-isolation.md) | 九张初始待确认9/9，确认后false9/9 | 真实模型仍有R02错分类；这是确认状态验收，不是属性准确率；额度9、模型尝试12 |
| [T15删除与缩略图](docs/reports/t15-experience.md) | 新增4后端+5前端测试；七张375×812截图无溢出 | 删除和照片使用临时库真实接口，编排为验收进程client层离线注入；不计新增真实模型验收 |

v3归因按样本分别统计：R单次IN=1；B的BENCH=3、T9依赖=6。B03的现有属性无法表达其外套断言，expect保持原样；B05/B10等待T9交互。不同分母不相加为“通过数/24”。[原文目录](docs/reports/raw/compose_v3/)包含每轮请求结果、重试反馈与聚合，可逐条复核。

## 验证与评测

```bash
make test
make lint
```

当前main全量结果为332 pytest + 44 Vitest通过，lint通过，来源见[任务板](docs/tasks.md)。单测离线注入失败，真实评测的B类仍走过滤→编排→client.chat；单元测试通过数与模型评测分母分别统计。

以下为已完成v3的溯源命令：

```bash
.venv/bin/python -m scripts.evaluate --repeats 3 \
  --recognition-dir docs/reports/raw/recognition_v2 \
  --output docs/reports/eval_v3.md --raw-dir docs/reports/raw
```

`--repeats`默认1，官方基线使用1；大于1仅对B类生效。`make eval`也是单次入口。已有报告或部分原文会触发拒绝覆盖，不发新模型请求；已提交的报告可直接读取。识别prompt最多到v2，本轮不出v3。

## 当前交付边界

- **已验证**：本地双服务、衣柜GET/PATCH/单品DELETE、规则筛选、真实编排API与方案页、硬约束校验、缺件卡、可关闭降级黄条、方案图片预览、375px截图及版本化评测；T15图片故障和编排注入边界单独标注。
- **照片建档已验证**：九张真实浏览器上传、识别、校正审计入库及卡片渲染；同draft重传不重复建档。375px无溢出，失败保留照片/占位可原地重试；所有上传均走逐件确认，置信度只辅助展示。
- **待完成**：T9换一套与排除交互；完整60秒演示尚未录制，仍缺T9交互。T12文档已整理，整体保持🟡。
- **未测量**：人工可穿率、HTTP端到端P95、完整首次建档耗时；不填写相应成效数字。
- **部署边界**：T14配置保留在独立codex/t14-ready分支，Docker未构建验证，未合入main；没有公开线上地址。本轮作品材料补齐不推进部署。

## 文件入口

| 文件 | 用途 |
|---|---|
| [作品说明](docs/作品说明.md) | 面向评审的五项作品信息、截图与验收结论入口 |
| [AGENTS.md](AGENTS.md) | 项目约束与验收纪律 |
| [任务板](docs/tasks.md) | 进度和真实命令证据 |
| [决策](docs/decisions.md) / [技术方案](docs/03-MVP与技术方案.md) | 设计依据与当前实现边界 |
| [cases.json](cases/cases.json) | 唯一基准衣柜、过滤规则及用例断言 |
| [评测脚本](scripts/evaluate.py) | 重放识别、真实组合、失败注入与重复采样 |
| [简历文案](docs/05-简历文案.md) | 仅使用已验证数字的项目描述 |

## 仅本地开发：认领历史数据

T13迁移将无归属旧数据明确标为`legacy`，普通设备不能查询。新设备不会自动收到原有24件测试衣物。
以下脚本**仅本地开发**，不提供线上API；认领会把legacy四张业务表归到指定设备。先备份，再执行：

```bash
# 默认dry-run，只打印件数，不写库
.venv/bin/python -m scripts.claim_legacy --device-id <uuid>
# 明确确认后才执行
.venv/bin/python -m scripts.claim_legacy --device-id <uuid> --apply
```

新设备的开发基准衣柜可以用`.venv/bin/python -m scripts.seed --owner-id <uuid>`生成；默认`make seed`仍隔离归legacy，不对新设备公开。

设备数据清空接口：`DELETE /api/wardrobe/items`，必须带本设备`X-Device-ID`；删除四张业务表及照片，当日匿名额度保留至次日0点。[隐私说明](docs/08-隐私政策.md)。

T13已完成：[隔离/配额/确认报告](docs/reports/t13-data-isolation.md)。识别20张/编排30次按北京时间每日重置，设备清空保留当日匿名额度；对外ID不含设备UUID，业务响应禁止缓存。历史`scripts/e2e_probe.py`尚未适配设备头，不作为当前验收入口。
