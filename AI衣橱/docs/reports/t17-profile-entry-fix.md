# T17 · GitHub主页体验入口更新

日期：2026-11-20。用户反馈GitHub上的体验入口无法打开，授权更新。

## 原因与修复

公开仓库private=false，不是权限问题。GitHub个人主页由仓库根README.md展示，其体验按钮仍指向https://53d43a3c36282c.app.lhr.life/；上轮仅同步AI衣橱/子目录，未更新主页按钮。旧主页地址和上轮6d9c7acc5fef3d地址本次匿名GET均返回502，正文no tunnel。后台分享继续运行，状态已轮换至https://8392ed6dc1c1ad.app.lhr.life。

本轮只把远端根README的体验按钮更新为当前已验地址，并标注2026-11-20临时链接更新时间。保留原主页其他段落和源码入口，不改变公开权限、产品代码或运行配额；旧报告中的历史地址不改写。项目内只新增本报告、更新任务板/CHANGELOG。

## 验证

匿名HTTPS检查：新地址首页200，/health200且正文status=ok。发布候选tree只允许根README与AI衣橱/下本次3个文档变化，其他blob SHA/type/mode必须不变；更新main使用expected_sha且不强推，发布后回读根README并重新提取体验按钮检查。

本地命令：zsh -ilc 'make test && make lint'，退出0：

```text
409 passed in 4.32s
Tests 76 passed (76)
All checks passed!
cd web && npx tsc --noEmit
```

## 边界

链接仍是免费临时通道，电脑需保持开机联网；轮换或停用后主页按钮需再次更新。本次没有长期托管、固定域名、新增模型调用或发布求职材料；数据仍在本机独立分享库。无法据此保证所有运营商/微信内置浏览器网络条件。
