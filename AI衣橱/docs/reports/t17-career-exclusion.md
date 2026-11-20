# T17：公开版本排除专用求职材料

日期：2026-11-20。

## 范围与结果

按人类要求，从公开仓库 `AI-mango-creator/AI-mango-creator` 的 `AI衣橱/` 当前版本删除：

- `docs/05-简历文案.md`
- `docs/作品说明.md`

两份原稿保留在本地，内容SHA256与操作前备份一致，已取消Git跟踪。`.gitignore` 排除简历、求职、面试、投递命名的文件及上述作品说明；以后按Git跟踪文件同步时不会重传。README移除两份材料的入口。技术文档中的历史任务记录和冻结评测证据保留，产品代码未改。

GitHub删除提交：[7dc181567d02ee94349d99e0e10728c2db3e0366](https://github.com/AI-mango-creator/AI-mango-creator/commit/7dc181567d02ee94349d99e0e10728c2db3e0366)。正常前进更新main，使用expected_sha校验，未强推。更新后回读main指向该提交；候选完整递归tree无截断，两份路径不存在，项目文件456项，其余文件SHA不变，项目目录外文件不变。随后仅补充本次清理记录、任务板及变更日志；记录也纳入Git跟踪文件同步范围。

## 本地验证

命令：`zsh -ilc 'make test && make lint'`，退出码0。

```text
394 passed in 4.08s
Test Files  10 passed (10)
Tests  65 passed (65)
All checks passed!
cd web && npx tsc --noEmit
```

专项检查：

```text
local originals=2 preserved; tracked=0; ignored=2; README links=0; poll-resumed screenshot unaffected
frozen=134; mismatches=[]
```

通过 `git ls-files`、`git check-ignore`、README链接检查及冻结清单SHA256逐项复核。排除规则未误伤技术截图 `12-poll-resumed-injected.png`。页面和接口没有变化，本轮未新增页面人工验收或截图，也未新增模型调用、试穿调用、部署或临时通道。

## 限制

普通删除只移除当前版本，旧GitHub提交仍可能查到历史副本。本轮不重写本地或远端历史。Git忽略规则不能阻止人为使用 `git add -f`，也不能阻止绕过Git文件清单的手工上传；正常后续同步须继续以Git跟踪文件为准。
