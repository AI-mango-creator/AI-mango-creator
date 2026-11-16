# AGENTS.md — 算法衣橱 Wardrobe Copilot

> 本文件是本项目的**唯一宪法**。任何与本文冲突的临时指令，以本文为准；如确需突破，先在 PR 说明里写「破例原因 + 影响面」，由人类批准后再改本文。
> 修改本文件本身 = 修改项目约束，必须单独一次提交，不得与其他改动混在一起。

---

## 0. 一句话

**输入「我的衣柜 + 今天的场景」，输出「3 套今天能直接穿出门的搭配 + 理由 + 缺件提示」。**

不是穿搭灵感库，不是购物推荐器，是**早上 7:50 替你做完决策的机器**。

---

## 1. 不可协商的产品约束

这四条来自真实用户访谈，任何实现方案都必须满足，不满足就是方向错了：

| 编号 | 约束 | 量化线 | 违反后果 |
|---|---|---|---|
| P1 | **建档成本必须极低** | 首次录入 ≤ 3 分钟、≤ 10 张照片 | 用户 3 天内弃用（这是竞品失败的首要原因） |
| P2 | **方案只能来自用户衣柜** | 衣柜外单品出现率 = 0 | 用户无法执行，产品归零 |
| P3 | **必须有理由，且理由可核对** | 每套 1 句话，须引用真实属性（温度/正式度/颜色） | 变成黑盒，用户不信 |
| P4 | **没有合适方案时要说没有** | 禁止硬凑 3 套 | 输出垃圾比不输出更伤信任 |

> 推论：**宁可不做，也不要做「AI 随机生成好看的图」**。这是本项目和「AI 穿搭图片生成器」的根本区别，写代码前必须理解。

---

## 2. 当前阶段

**P0 · 单链路验证阶段。** 只做一条链路，做穿、可验收、有失败兜底。

P0 明确**不做**（写进 checklist，不要"顺手实现"）：
- 用户注册登录、多设备同步
- 3D 人体建模、点云重建、Unity / AR
- **虚拟试穿**（P1 才做，且只允许走托管推理 API，禁止自部署）
- 电商链接抓取、商品比价、分佣、退货率数据
- 社交分享、穿搭社区、案例广场
- 会员付费、积分体系、文小言生态联动
- 多语言、深色模式、无障碍

如果某个需求实现不了，**停下来提问**，不要用假数据糊过去。

---

## 3. 技术栈（禁止擅自更换）

```
前端  React 18 + TypeScript + Vite + Tailwind CSS
      移动优先，基准视口 375×812，最大宽度 480 居中
      状态：zustand（仅一个 store，不要引 redux / react-query）

后端  FastAPI + Python 3.11 + Pydantic v2
存储  SQLite（data/app.db）+ 本地文件（data/uploads/）
AI    唯一出口 app/llm/client.py；视觉识别与文本编排分开两个函数
测试  pytest（后端）+ vitest（前端）+ 自建跑批脚本 scripts/evaluate.py
```

**禁用清单**：Docker、Kubernetes、微服务、Redis、Celery、GraphQL、任何需要联网的第三方数据库、任何需要付费账号的第三方 SDK。

**P0 额外禁用（见 `docs/decisions.md` D7）**：本地模型权重下载、Paddle / PaddleDetection / PaddleClas、SAM、detectron2、diffusers、torch 本地推理、任何 GPU 依赖。P0 的 AI 能力**只允许 2 类远程调用**——识别与编排；"2" 指能力种类，每类单次请求最多 3 次调用（首调 1 + 重试 2，见 D7.1），不是总共只能调 2 次。本机是 16GB MacBook Air，跑不动 7B 视觉模型。

理由：这是要在笔记本上 `make dev` 就能跑、面试时能当场演示的项目。引入任何需要额外启动步骤的组件都是减分。

### 3.1 本机运行环境（已装好，禁止改用"内置运行时"）

| 依赖 | 位置 | 自查命令 | 现状 |
|---|---|---|---|
| Node 22 LTS | `~/.local/bin/node`（指向 `~/.local/node/node-v22.23.5-darwin-arm64`） | `node -v` | v22.23.5 / npm 10.9.9 |
| Python 3.11 | 仓库内 `.venv/`（由 `uv` 创建） | `.venv/bin/python -V` | 3.11 |
| uv | `~/.local/bin/uv` | `uv --version` | 0.13.6 |

规则：

1. **验收必须用人类终端里能复现的同一条命令**。若 `node` / `npm` 报 command not found，先用 `zsh -ilc 'node -v'` 或绝对路径 `~/.local/bin/node` 复核；**不得改用宿主应用自带运行时、也不得静默跳过该验证项**——"我这边能跑"不算验证，见 §6.5。
2. 禁止 `sudo`、禁止改系统 PATH、禁止 `npm i -g` 装非必要工具；需要全局安装先问人类。
3. `web/node_modules` 一旦存在即视为基线，**不要删除重装**（重装会引入版本漂移，让"昨天还绿今天红了"）。
4. Python 一律用 `.venv/bin/python`，禁止裸 `python3`（版本不对会静默装上不同 wheel）。

---

## 4. 目录结构（新增文件必须落在既有目录内，不得新建顶层目录）

```
.
├── AGENTS.md
├── Makefile
├── .env.example
├── docs/                  # 只有文档
│   ├── prd-提炼.md
│   ├── 01-项目定位与链路.md
│   ├── 02-codex对话脚本.md
│   ├── 03-MVP与技术方案.md
│   ├── 04-验收标准与失败处理.md
│   ├── 05-简历文案.md
│   ├── decisions.md       # D1–D7 已定稿决策，改它要单独提交
│   ├── tasks.md           # 任务板 + 状态，唯一进度真相
│   └── reports/           # evaluate.py 生成的报告，按版本号命名
├── prompts/               # 所有 LLM prompt，Markdown，带版本号
│   ├── vision_extract.v1.md
│   ├── outfit_compose.v1.md
│   └── compose_fallback.v1.md
├── cases/                 # 评测用例，JSON
│   └── cases.json         # 唯一数据源：wardrobe(12 件基准衣柜) + 20 条用例
│                          # 禁止再拆出 wardrobe.json —— 两份衣柜数据必然漂移，
│                          # T4 单测与 T10 跑批各读一份就会出现"过滤过了 eval 挂了"
├── scripts/
│   └── evaluate.py        # 跑批入口，输出 reports/eval_vN.md
├── app/                   # 后端
│   ├── main.py
│   ├── models.py          # Pydantic 模型 = 唯一数据结构真相
│   ├── db.py
│   ├── llm/client.py
│   ├── services/
│   │   ├── extract.py     # 照片 → 单品结构化
│   │   ├── filter.py      # 场景 → 候选集
│   │   ├── compose.py     # 候选集 → 3 套方案
│   │   └── validate.py    # 硬约束校验器
│   └── routers/
└── web/                   # 前端
    └── src/{pages,components,api,store}
```

---

## 5. 命令（Makefile 里必须都有，缺一个都不算完成）

```bash
make dev      # 同时起后端 :8000 与前端 :5173
make test     # pytest -q && vitest run
make lint     # ruff check app && tsc --noEmit
make seed     # 灌入 cases/wardrobe.json 作为默认衣柜
make eval     # 跑 20 条 case，生成 docs/reports/eval_vN.md
```

---

## 6. 硬性工程规则（违反即返工，不接受"下个版本再改"）

### 6.1 LLM 调用
1. 所有 LLM 调用必须走 `app/llm/client.py`，**禁止在 service 层直接 import SDK**。
2. 输出一律**结构化 + Pydantic 校验**；禁止对模型返回文本做正则/裸 `json.loads` 猜字段。
3. 每次调用必须带：`timeout=20s`、`max_retries=2`、`max_tokens` 上限、`temperature` 显式指定（编排用 0.3，识别用 0）。
4. prompt 全部放 `prompts/*.md`，文件名带 `.vN`；**改 prompt 必须在汇报里贴改动前后 diff 摘要 + 是否影响既有 case**。
5. 每次调用写一条日志到 `data/llm.log`：`case_id / prompt_version / 耗时 / prompt_tokens / completion_tokens / 是否降级`。

### 6.2 数据
6. 数据库结构变更必须附 `app/migrations/NNN_xxx.sql`，**禁止删列、禁止 DROP TABLE**。
7. `app/models.py` 是数据结构唯一真相；改模型必须同步改 `cases/*.json` 的字段，并在汇报里说明。
8. 用户上传的图片只存本地 `data/uploads/`，**不得上传到任何第三方存储**；日志里不得出现图片 base64。

### 6.3 前端
9. 375px 视口下不得出现横向滚动；所有页面必须有 **loading / empty / error** 三态。
10. 禁止把 API Key 或任何 token 打进前端 bundle；前端只能调自己的后端。

### 6.4 失败
11. 任何失败路径都必须返回**用户可读的中文文案**，禁止把 500 / traceback 暴露给前端。
12. 降级路径必须显式标记（前端顶部 show 一条「AI 暂不可用，以下为基础搭配」），**禁止静默降级**。

### 6.5 测试纪律
13. **禁止删除、跳过（skip/xfail）、放宽** `tests/` 或 `cases/` 里的内容来让测试变绿。测试挂了就改实现。
14. 修改 `cases/` 里的期望值，必须单独提交并写明「原期望错在哪」，不能混在功能提交里。
15. 通过标准写死在 `docs/04-验收标准与失败处理.md`，**任何情况下不得为了让报告好看而调低标准**。

---

## 7. 每个任务的完成定义（DoD）

一个任务只有全部满足才算完成，缺项要明说"未完成，原因是X"：

- [ ] 有对应测试（后端 pytest）或 case（评测）
- [ ] `make test` 全绿、`make lint` 无 error
- [ ] 375px 视口人工过一遍，三态齐全
- [ ] `CHANGELOG.md` 追加一行（日期 + 任务 + 影响面）
- [ ] 汇报三段式（见 §8）
- [ ] 没有超出本任务范围的文件改动（`git status` 自查）

---

## 8. 汇报纪律（每次结束必须输出这三段）

```
## 改了什么
- 文件清单（新增/修改），每个一句话说明为什么改

## 怎么验证的
- 执行的命令 + 关键输出（真实粘贴，不要复述）
- 人工检查点：哪几个页面/哪几个 case 实际看过

## 遗留与风险
- 未做的、不确定的、需要我拍板的
- 你认为下次可能翻车的地方
```

**不确定就问，不要猜着写。** 一次追问消耗 30 秒，猜错重写消耗半小时。

---

## 9. 一次只做一件事

- 一个对话窗口只推进 `docs/tasks.md` 里**一个**任务（任务清单以 `tasks.md` 为准，`docs/03` 第七节只是模板）。
- 任务开始前先复述「我要做什么、验收标准是什么、会碰哪些文件」，等我确认再动手。
- 任务完成后**必须更新 `docs/tasks.md` 的状态列与"实测证据"列**，再提交；没更新状态视为任务未完成（简历里的进度数字直接从这张表来）。
- 单次改动**不超过 8 个文件**；超过说明任务切分不够细，先拆再写。
- 计数口径：只数**代码/配置/数据**文件（`app/`、`web/`、`scripts/`、`cases/`、`Makefile`、`package.json` 等）。`CHANGELOG.md`、`docs/*.md`、`docs/reports/*` 属于 DoD 强制产物，**不计入上限**。
- 发现要做的事超出当前任务范围，**停下来记录到 `docs/backlog.md`**，不要顺手做。

---

## 10. 三条红线（踩到直接回滚）

1. **用 mock 数据冒充真实链路**：允许在测试里 mock LLM，但 `make dev` 跑起来的必须是真链路，且 mock 必须在 UI 上有明确标识。
2. **推荐了衣柜里没有的衣服**：这是 P2 红线，验收里出现一次即不通过。
3. **为了让指标好看而改标准**：宁可报告难看，不可报告失真。
