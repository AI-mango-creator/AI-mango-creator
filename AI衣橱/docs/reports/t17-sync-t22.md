# T17 · T22同步GitHub与手机临时体验链接

日期：2026-11-20。人类要求同步至GitHub，并提供手机可直接打开的体验链接。仅发布现有已验代码与文档，不变更产品功能、不新增模型调用；继续排除简历材料和运行数据。

## GitHub

公开目标：AI-mango-creator/AI-mango-creator，AI衣橱/目录。

本地906c89e的509项Git跟踪文件已同步，新增/更新70项（44文本+26截图）；未上传.env、data、.venv、node_modules、原始人物/用户照片或本地备份。docs/05-简历文案.md与docs/作品说明.md保留本地、保持忽略，不在Git文件清单中。宽松凭据规则曾误命中历史截图文件名task-lost-response中的sk-子串，已复核为路径文本；采用词界及真实配置密钥逐值检查后均0命中，未修改冻结证据。

快照提交：[64c1135d80166be8eab1d5d0dbbc013cd15a568c](https://github.com/AI-mango-creator/AI-mango-creator/commit/64c1135d80166be8eab1d5d0dbbc013cd15a568c)，更新main后已回读。基于原head正常前进，expected_sha校验，未强推。递归tree未截断，逐文件Git blob SHA/type/mode核验：

```text
files=509; missing=0; mismatch=0; extra=0; outsideChanged=0
forbidden=[]; credentialPatternHits=0; configuredKeyMatches=0
```

本报告、任务板与CHANGELOG作为后续同步记录另补；原主页及项目目录外文件不改。仅上传当前快照，不上传本地Git历史，也不恢复此前已删除的求职材料。

## 手机临时链接

[本次临时体验地址](https://6d9c7acc5fef3d.app.lhr.life)。使用已有scripts.share后台启动；本机保持开机联网，临时通道关闭或轮换后旧地址可能失效。不是长期部署，GitHub源码入口也不是在线后端。后续先运行`.venv/bin/python -m scripts.share --status`查询并校验最新地址，不能从本文历史记录假定仍然可用。

运行命令：`zsh -ilc '.venv/bin/python -m scripts.share --background'`。独立分享库data/share/app.db、照片/日志/盐均在data/share，不复制本机原衣柜。后台进程及通道保持运行，不依赖本轮工具会话；全站每日识别20张、生成30次，保留原每设备与T21限制，没有追加人民币预算或解除真实试穿资源限制。

真实HTTPS检查：

```text
health=200; home=200; currentAppAsset=200
withDevice=200; noDevice=400; T22Points=200
```

已核验公网App JS字节与本机当前生产构建完全一致；新测试设备衣柜为空、积分只读为0。未用localhost/LAN地址冒充公网地址，未新增真实识别/生成/试穿调用；本轮没有物理手机实机操作，交互375×812证据沿用T22实际浏览器验收。

## 本地回归

`zsh -ilc 'make test && make lint'`退出0：

```text
409 passed in 4.07s
Test Files  12 passed (12)
Tests  76 passed (76)
All checks passed!
cd web && npx tsc --noEmit
```

分享启动再次构建生产网页成功（401ms），启动脚本校验当前后端密钥未进入bundle。134项冻结证据此前T22收尾已核验，本次不改这些文件。当前任务只写同步文档、任务板与CHANGELOG，产品代码不改。

## 遗留

电脑合盖、断网、关机或免费通道失效会中断；本轮不能承诺永久地址。模型实际调用仍会消耗现有账号额度，免费通道图片传输可能较慢。真实试穿效果与资源待T21安排，不因这次可访问就改称已验证。旧GitHub提交中的历史求职文档未重写，本次当前版本继续排除。
