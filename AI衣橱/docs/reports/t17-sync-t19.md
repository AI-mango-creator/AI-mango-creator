# T17 · T19改版同步GitHub

日期：2026-11-18。用户明确要求同步现有项目，沿用公开主页仓库AI-mango-creator/AI-mango-creator的AI衣橱/目录。此次同步代码与文档快照，不修改功能、不上传本地Git历史。

## 同步证据

- 源：本地main f9070c8，358个Git跟踪文件。
- 原远端main：38c564277cf36476364658b367c68e84befdd8fc。
- 项目快照提交：6874d2921aee6e33bf397e1b3cfa34cedefe72ec。
- 新增/更新59项：32文本、27张验收截图。包含首页、城市天气后端/七天预报页、档案与衣橱改版、原始天气响应、设计计划及任务记录。
- 发布前候选tree逐项对照全部358文件Git blob SHA与mode：missing=0、mismatch=0、extra=0。AI衣橱/外的主页文件变更0。
- 在原head基础创建提交，expected_sha检查并正常前进，不强推。一个截图上传的临时失败已重新上传并校验原SHA一致。
- 随后追加本报告、CHANGELOG及tasks同步证据，以独立文档提交同步；不改产品文件。

## 本地检查

`zsh -ilc 'make test && make lint'`，exit0：

```text
355 passed in 3.10s
Tests 50 passed (50)
All checks passed!
cd web && npx tsc --noEmit
```

发布审计：

```text
publish audit: 358 tracked files; excluded runtime paths=0; credential-pattern hits=0; frozen 134/134 unchanged
```

未上传.env、data/、.venv/、node_modules/、web/dist/，不含设备私有衣柜及照片。新增截图明确区分真实天气、UI注入与隔离测试衣柜；本轮不重新调用模型/天气接口，天气与27张375×812截图沿用T19实测证据。

## 入口与边界

- [项目代码与说明](https://github.com/AI-mango-creator/AI-mango-creator/tree/main/AI%E8%A1%A3%E6%A9%B1)
- [T19页面及天气验收](t19-home-weather.md)
- [项目快照提交](https://github.com/AI-mango-creator/AI-mango-creator/commit/6874d2921aee6e33bf397e1b3cfa34cedefe72ec)

GitHub用于浏览源码、文档和截图。此同步不会将FastAPI部署上线，也不会开启临时公网交互链接。
