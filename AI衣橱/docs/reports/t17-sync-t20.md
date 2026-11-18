# T17 · T20真实社区同步GitHub

日期：2026-11-19。用户要求同步至GitHub主页，沿用公开仓库AI-mango-creator/AI-mango-creator的AI衣橱/目录。不改产品功能，不上传本地Git历史。

## 同步内容与核验

- 源：本地main `eff55df`，413个Git跟踪文件。
- 原远端main：`d692082d6442e274363c4e0fb4389bf640474eba`。
- 项目快照提交：`9daabff8e313de8220ad947c37c51ca96fcf1685`；已回读远端main确认指向该提交。
- 新增/更新70项：36项代码/配置/文档/数据记录，34张375×812验收截图。包含真实社区八表与接口、四类发布及关注/赞/评论/投票、衣橱搭配导航合并、隐私说明与独立审查修复。
- 发布前候选tree逐项对照全部413文件的Git blob SHA、type和mode：missing=0、mismatch=0、extra=0。AI衣橱/外主页文件变更0。
- 在原head基础提交，expected_sha校验、正常前进，不强推；二进制截图逐张核对原SHA。部分连接临时中断后只重传对应blob或重读head，没有绕过验证。
- 本报告、CHANGELOG和任务板的同步证据以随后独立文档提交补入，不修改产品文件；避免报告引用自身提交哈希。

## 本地检查

命令：`zsh -ilc 'make test && make lint'`，exit0：

```text
373 passed in 4.08s
Tests 57 passed (57)
All checks passed!
cd web && npx tsc --noEmit
```

发布前审计：

```text
tracked=413
runtime_paths=0
credential_pattern_hits=0
frozen_unchanged=134
```

没有上传.env、data/、.venv/、node_modules/或web/dist/。本轮无模型/天气调用、无新公网服务；双设备交互与截图沿用已完成的[T20真实验收](t20-community.md)，未重做浏览器或将临时测试数据灌入实际社区。

## 入口

- [AI衣橱源码与作品说明](https://github.com/AI-mango-creator/AI-mango-creator/tree/main/AI%E8%A1%A3%E6%A9%B1)
- [T20社区验收报告](https://github.com/AI-mango-creator/AI-mango-creator/blob/main/AI%E8%A1%A3%E6%A9%B1/docs/reports/t20-community.md)
- [项目快照提交](https://github.com/AI-mango-creator/AI-mango-creator/commit/9daabff8e313de8220ad947c37c51ca96fcf1685)

GitHub链接用于查看源码、文档和截图，此同步不等于部署FastAPI，也不提供常驻公网交互地址。
