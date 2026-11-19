# T17 · T21离线试穿体验同步GitHub

日期：2026-11-19。用户明确要求同步GitHub，沿用公开主页仓库AI-mango-creator/AI-mango-creator的AI衣橱/目录。不改产品功能，不上传本地Git历史。

## 同步内容与核验

- 源：本地main `3d742e7`，457个Git跟踪文件。
- 原远端main：`44822fd4550dea0d35b7063ee3d3cc1524a74007`。
- 项目快照提交：`f1137c852f6a999201c7eb8dc0bf3f845744b471`，已回读远端main确认。
- 新增/更新58项：35项代码/配置/文档/记录，23张离线375×812截图。包含体验目录/详情、人物选择、私有异步试穿/额度与拒重、清空、客户端、导入脚本及验收说明。
- 候选tree逐项对照全部457文件Git blob SHA、type、mode：missing=0、mismatch=0、extra=0，AI衣橱/外主页文件变更0。每张截图上传后核对原始blob SHA。
- 基于原head创建提交，expected_sha校验、正常前进，不强推。
- 本报告、CHANGELOG及任务板随后以独立文档提交补入，避免报告引用自身提交哈希。

## 本地检查

`zsh -ilc 'make test && make lint'`，exit0：

```text
394 passed in 3.76s
Tests 65 passed (65)
All checks passed!
cd web && npx tsc --noEmit
```

发布审计：

```text
tracked=457
excluded_runtime_paths=0
credential_pattern_hits=0
frozen_unchanged=134
```

没有上传.env、data/（含本地库、备份、人物/结果照片）、.venv/、node_modules/或web/dist/。公开截图只有明确标注的离线夹具，不能作为真人试穿效果或供应商速度证据。T21仍🟡，真实试穿生成0次，默认目录尚待授权素材。

本轮仅同步已有实现和证据，没有重做浏览器验收、调用真实模型/天气/试穿服务、注册充值或开启公网服务。

## 入口与边界

- [AI衣橱源码与说明](https://github.com/AI-mango-creator/AI-mango-creator/tree/main/AI%E8%A1%A3%E6%A9%B1)
- [T21离线验收报告](https://github.com/AI-mango-creator/AI-mango-creator/blob/main/AI%E8%A1%A3%E6%A9%B1/docs/reports/t21-tryon-experience.md)
- [项目快照提交](https://github.com/AI-mango-creator/AI-mango-creator/commit/f1137c852f6a999201c7eb8dc0bf3f845744b471)

GitHub用于查看源码、文档与截图，本次同步不等于部署后端或启用真实试穿；人物素材、账号及费用验证仍按T21后续安排。
