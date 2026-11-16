# T16 · 临时HTTPS交互测试版

日期：2026-11-16，Asia/Shanghai。实现范围为批准的六个代码/配置文件，文档另计。未改模型、prompt、cases断言、旧验收证据或已有测试；未部署云服务器或Docker。

## 已实现与执行口径

| 改动文件 | 用途 |
|---|---|
| app/db.py | 可配置独立数据目录，分享模式全站额度在写事务内扣减 |
| app/llm/client.py | 仅LOG_PATH跟随数据目录，不改模型调用或日志字段 |
| app/main.py | 显式分享配置下提供生产网页与assets，保留原API和设备校验 |
| app/tests/test_share.py | 新增12项临时库/子进程/额度/启动失败回归测试 |
| scripts/share.py | 构建、通道、真实健康检查、配额配置及进程清理 |
| Makefile | 新增make share入口，make dev不依赖分享工具 |

同步README、临时测试指南、任务板和CHANGELOG，新增本轮报告/浏览器记录/截图。没有变更既有测试、模型schema、依赖、prompt或cases。

- `make share`：生产前端构建、127.0.0.1:18080网页/API同址服务、独立`data/share/app.db`与uploads、临时HTTPS通道。只在公网health实测200后公布地址；配置缺失、端口占用、网络失败返回中文说明，不伪造成功。
- 仅分享模式增加全站北京时间每日识别20张/生成30次，仍保留每设备20/30；同一SQLite写事务内统计和增加，更换UUID、并发或清空业务数据不重置当日全站用量。模型重试共用既有D7.1预算。
- 默认本地`make dev`的数据路径/额度行为不变；client.py只改LOG_PATH，日志字段/脱敏和真实模型默认路径不动。分享版不导入legacy或原用户衣柜；数据库结构没有变化。
- 仅公开根网页和`/assets`构建资源，API照片仍按设备头读取。公网实测`/`200、`/health`200、`/.env`404、`/data/app.db`404；前端构建未包含当前API密钥。

## 通道实际问题与修复

1. 从官方release下载cloudflared 2026.11.0至`data/tools/`，校验SHA256 `8c2f90277ef06a6080bb40b964d33f09f1188102f8798f2e344174b6cf41accf`，未安装全局工具或npm/pip依赖。
2. Cloudflare在本机网络失败：日志有`hard_fail=true`、`Allow outbound TCP on port 7844`、`TLS handshake with edge error: EOF`；打印的域名不能连通，**未算发布成功**。
3. 使用系统SSH的localhost.run备用通道，端口22可连，443失败；不读取用户SSH配置/agent/私钥，TOFU主机记录仅存忽略目录。免费域名实际为多级`.app.lhr.life`；最初正则只接受一层域名导致识别失败，按真实日志补回归后修复。
4. 首次失败退出时日志线程在文件关闭后写入，已改为子进程直接写日志文件，移除写文件线程；失败启动退出后18080释放。只读审查另发现配置错误LLMError漏捕获，补先RED再GREEN的回归测试并修复。

通道与程序实际日志留在忽略提交的`data/share/`；稳定运行后会记录上次成功通道，后续`make share`优先复用，无需每次等待失败的Cloudflare。

## 真实公网完整链路（无注入）

首轮公网域名：`https://719175e281768e.app.lhr.life`，用于以下真实验收，后续停启会更换，**不是永久访问地址**。原始浏览器记录见[t16-browser.json](t16-browser.json)。

Chrome CDP模拟375×812，从公网网页通过Vite生产构建实际界面选择文件，走公网multipart→现有vision→解析/校正→SQLite→照片卡片→显式确认→真实chat→校验→方案。没有模型/HTTP成功响应注入。

| 输入 | 浏览器驱动观测耗时（见下方口径） | 确认结果 |
|---|---:|---|
| R05 / cloth05.jpg 上衣 | 9561ms | needs_confirm解除 |
| R03 / cloth03.jpg 裤子 | 23153ms | needs_confirm解除 |
| R08 / cloth08.jpg 鞋 | 48055ms | needs_confirm解除 |

驱动观测9561–48055ms，n=3，不含点击确认或拍摄/系统相册选择。**初版驱动只检查页面任意已加载的图片，后两次可能命中旧卡照片；原JSON字段upload_to_photo_ms保留但不能按字面当作每张新照片的完整加载耗时。** 这三个数只记录本次操作观测，不与T5本地九张完整建档计时混算，不报告平均或P95；自动点击确认只验证状态通路，不代表识别属性已经人工评定全对。三笔POST均真实201，库新增三件可读取记录。

20℃/周末：POST /api/outfits 200，**1套、degraded=false、latency_ms=5026、outfit_compose.v1**。三个槽位都来自本次上传；只有一组可组合衣物，如实返回1套，未硬凑3套。实际模型调用共4次（3识别+1编排），日志耗时分别5892/4605/6039/5014ms；业务额度识别3、编排1。

**已知体验限制必须保留**：方案同时加载三张照片时，免费通道使照片请求超过既有10s截止时间，三张均显示品类·子类文字块；初次“全部图片可见”的浏览器等待因此失败，原始失败字段和[当时截图](ui-t16/99-failure.png)保留。没有因此改断言或延长原API超时；搭配生成、理由和衣柜照片仍可用。文字降级是既有T15行为，但本轮不能宣称“公网方案三张图片均正常显示”。

## 两设备与视口

两个独立浏览器上下文模拟不同设备：A3件、B0件；B访问A照片404。Runtime异常0；截图width=scrollWidth=375、height812，没有横向溢出。新增截图已实际查看：

补拍时发现新浏览器窗口会干扰无头视口，已对每个Target重新设置CDP设备模拟，同时读取实际PNG头验证375×812后才纳入证据；未重调模型，未修改产品或用例。

- [公网初始空衣柜](ui-t16/00-public-empty.png)
- [三件真实照片入柜并确认](ui-t16/01-public-three-items.png)
- [真实方案及照片文字降级](ui-t16/02-public-outfit.png)
- [另一设备空衣柜](ui-t16/03-other-device-empty.png)

## 自动化与停启验收

```text
.venv/bin/python -m pytest -q app/tests/test_share.py
12 passed in 0.40s

zsh -ilc 'make test'
295 passed in 2.47s
Tests 34 passed (34)

zsh -ilc 'make lint'
All checks passed!
tsc exit 0

.venv/bin/python -m ruff check scripts/share.py
All checks passed!
```

新增12条测试覆盖同址网页/API/静态边界、独立库和日志、全站限额跨设备/并发、旧设备额度、清空不重置、父环境不变、子进程终止、安装摘要拒绝、真实免费域名解析及缺配置中文错误。原283条后端及34条前端测试均保留。

实际Ctrl-C结束首次分享后，`lsof -nP -iTCP:18080 -sTCP:LISTEN`无输出，`share.json`已移除；再用**同一条`zsh -ilc 'make share'`**重启，最终公开地址及检查以运行时`data/share/share.json`和下方补记为准。

### 最终停启补记

重启默认`make share`实际成功，生产构建355ms；上次成功的localhost.run通道自动优先使用，避免重复等待当前网络下失败的Cloudflare。最终启动打印：

```text
测试链接已连通：https://ec8a2c3f975574.app.lhr.life
全站每日识别20张/生成30次；原衣柜不在此测试库中。
```

最终域名再次实测：`/health`200、`/`200、新设备带头GET200且`[]`、无设备头400。这也是短期地址，会随免费通道轮换或停止而失效；永久运行地址不写死在README，重新启动以终端输出为准。没有为重启新增模型调用。

## 未做

无长期云部署、域名购买、账号注册、T9、试穿、模型更换或新prompt；没有导入原衣柜。手机视口验收来自真实Chrome设备模拟，不声称已做iPhone/Android实体机测试。临时链接依赖电脑和通道，免费带宽和域名轮换限制仍存在。

## 发布前保活补验（同一T16任务）

首次最终复查发现免费SSH空闲时超时，`ec8a…`旧地址已失效，因此不能将上一段启动成功视为持续可用。已增加约每15秒走公网`/health`保活、不调用模型；同时修复短暂502会过早结束整个分享的问题，保留本地服务等待网络恢复。SSH容错调整为30秒×10，但仍不承诺长期可用。

新增两条先RED后GREEN回归，验证空闲保活和短暂公网失败不停止服务。最终14项分享测试通过，全量`297 passed in 2.80s` + Vitest `Tests 34 passed (34)`，lint/脚本ruff通过。此前12项、295项记录为初轮结果，未删改任何既有测试。

本轮最终运行地址为`https://18062f6f12a188.app.lhr.life`，已连续约一分钟5次抽查health均200，分享进程始终存在；原始时间戳见[t16-keepalive.json](t16-keepalive.json)。后台保活期间模型调用日志仍共4条，没有追加识别或编排。当前地址仍只在进程运行/通道未轮换时有效。
