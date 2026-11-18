# T17 · T18增量同步GitHub

日期：2026-11-18。用户明确要求同步项目资料，沿用既有公开主页仓库及AI衣橱/目录；这是文件快照同步，不改产品功能或冻结证据，不上传本地Git历史。

- 源快照：本地main c6ffb75，312个Git跟踪文件。
- 目标：AI-mango-creator/AI-mango-creator，公开，main的AI衣橱/。
- 原远端head：252a248490aa6e7707a7af73cf83f8a99df4c718。
- 项目快照提交：d7d88aebb6f0bbadcd28107f4dea4a6051bd7df0，50项新增/更新（39文本+11截图）；在原head上正常前进，expected_sha校验，无强推。
- 发布前候选tree：a6b1e0fae2f81624038969435d979a334a34a8d9。完整递归tree核对312项Git blob SHA与mode：missing=0、hashOrModeMismatch=0、extra=0；AI衣橱/以外内容变更0。
- 发布后回读main，确认head为上述提交。随后追加本报告、CHANGELOG和任务板同步记录；该文档提交与项目代码分开，不修改产品文件。

## 本地验证

`zsh -ilc 'make test && make lint'`，exit0：

```text
332 passed in 3.02s
Tests 44 passed (44)
All checks passed!
cd web && npx tsc --noEmit
```

发布前安全/冻结检查输出：

```text
publish audit: 312 tracked files; no excluded runtime paths; credential-pattern hits=0; frozen 134/134 unchanged
```

仅使用Git跟踪文件；未包含.env、data/、.venv/、node_modules/、web/dist/，未上传设备私有衣柜或照片。本轮没有UI改动、模型调用和云部署；375px验收沿用已同步的T18报告及11张截图。新版prompt的真实识别/解释效果仍未验证，不以本次同步作为模型验收。

## 入口

- [AI衣橱项目](https://github.com/AI-mango-creator/AI-mango-creator/tree/main/AI%E8%A1%A3%E6%A9%B1)
- [T18验收报告](t18-profile-categories.md)
- [GitHub快照提交](https://github.com/AI-mango-creator/AI-mango-creator/commit/d7d88aebb6f0bbadcd28107f4dea4a6051bd7df0)

GitHub链接提供源码、说明与截图；公网交互服务本轮未开启，免费临时通道不会因同步源码而恢复。
