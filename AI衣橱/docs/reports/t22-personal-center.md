# T22 个人中心实施与验收

真实试穿调用0；仅本地开发，无GitHub同步或部署。


- T22-A: 398 passed in 3.95s; Vitest 65 passed; make lint exit0.

- T22-B: 404 passed in 4.19s; Vitest 65 passed; make lint exit0.

- T22-C: 408 passed in 4.82s; Vitest 65 passed; make lint exit0.

- T22-D: 408 passed in 5.48s; Vitest 70 passed; make lint exit0.

- T22-E: 408 passed in 4.58s; Vitest 70 passed; make lint exit0.

- T22-F: 408 passed in 4.24s; Vitest 73 passed; make lint exit0.


## 独立审查与修复

独立审查c3fa820..53d5e7c后发现5项，均已处理，不把审查通过等同于实际运行：

| 问题 | 验证与结果 |
|---|---|
| StrictMode复用已中止控制器，OOTD保存不返回 | 新回归先失败（onDone 0次）后通过；375×812开发模式真实选文件/提交，成功返回列表并打开详情。 |
| 历史打开可能查询供应商 | 增加设备隔离的只读本地快照接口；新增HTTP测试先404后200，供应商函数设置为调用即失败仍通过；前端按指定task_id读取该接口，历史任务不自动轮询。 |
| 慢第二页串入新标签 | CDP实际延迟历史第二页、切收藏、再放行：修前oldPageAppendedToFavorites=3，修后=0。取消所有该标签在途分页。 |
| 私密图片传输中设备变化 | 回归先显示ready后修为error；响应体读取后再次核验身份，storage变化释放照片ObjectURL。 |
| 设置子页和多层浏览器返回 | 子页写入浏览器历史，保存各层滚动位置；CDP设置→常见问题→浏览器返回，afterBrowserBack=设置。 |

技术裁决：为符合“历史读取不调用供应商”的严格验收口径，指定历史任务只读本地快照；相应按钮显示“读取本地记录”，需要实时任务观察时仍由原服饰试穿入口按T21限制处理。代价是历史详情不是实时轮询页面。沿用已批准功能分支原地实施，未额外创建worktree/重装依赖；审查修复按原C范围3文件和原D/E/F范围8文件分别提交，不扩大产品范围。

## 最终本地验证

命令：`zsh -ilc 'make test && make lint && cd web && npm run build'`，退出码0。真实输出：

```text
409 passed in 5.98s
Test Files  12 passed (12)
Tests  76 passed (76)
All checks passed!
cd web && npx tsc --noEmit
vite v7.3.8 building client environment for production...
✓ 64 modules transformed.
✓ built in 469ms
```

专项复核：

```text
frozen=134; mismatches=0
existing test_db assertions unchanged
career originals preserved, ignored, untracked=2
screenshots=26; width=375; overflow=0; runtimeErrors=0
```

test_db只增加7个模型import与新表expected条目，AST比较确认全部原有assert不变；其他旧测试断言未改，未修改prompt/cases/冻结报告或LLM日志。新增表009幂等创建，未DROP/删列；原推荐链路、设备头及AI日配额保持。

## 双设备真实HTTP与浏览器

验收使用独立临时SQLite和uploads，测试服务127.0.0.1:8022、开发网页5182；不写入用户现有衣柜。通过真实multipart上传已有项目测试衣物图片，创建私密OOTD、公开测试帖子与头像；试穿历史/衣柜搭配为明确标注的离线记录注入，**不是新生成效果**，供应商调用0。

```text
HTTP dual-device: check-in balance=10 after3; received=3 + follow1; favorites=1;
OOTD photo/outfit persisted and repeat-safe; foreign OOTD/avatar404;
feedback saved; provider calls=0
StrictMode browser OOTD save: success
oldPageAppendedToFavorites=0; expected=0
afterBrowserBack=设置; expected=设置
screenshots=26; maxWidth=375; runtimeErrors=0
clear: awarded=false, balance=0; otherPosts=1
```

浏览器最后清空的是隔离库A，B帖子仍1条，A当天重签不补领；单测另验清空恢复/回滚、下一天可领、相同草稿不重复、内容冲突409、删记录旧POST410、源方案删除变空引用。当前不声称头像公开、积分兑换、完整账号体系或实时通知推送。

## 页面实测截图

共26张，全为375×812、scrollWidth=375。注入失败截图标题带injected，历史截图也标注“隔离验收素材·非真实试穿”。完整尺寸与Runtime检查见[checks.json](ui-t22/checks.json)。

| 页面 | 证据 |
|---|---|
| 我的／五个内容标签 | [生成历史](ui-t22/01-my-history.png)、[收藏](ui-t22/02-favorites.png)、[发布](ui-t22/03-published.png)、[私密OOTD](ui-t22/04-ootd-private.png)、[搭配](ui-t22/05-outfits.png) |
| 积分／互动 | [积分明细](ui-t22/06-points-real.png)、[收到的互动](ui-t22/07-received-interactions.png) |
| 设置 | [上半页](ui-t22/08-settings-top.png)、[下半页](ui-t22/09-settings-bottom.png)、[头像昵称](ui-t22/10-edit-identity.png) |
| OOTD实际保存 | [新建](ui-t22/11-ootd-new-empty.png)、[选文件](ui-t22/12-ootd-selected-photo.png)、[保存后详情](ui-t22/13-ootd-saved-detail.png)、[编辑](ui-t22/14-ootd-edit.png) |
| 帖子收藏 | [真实收藏状态](ui-t22/15-post-bookmark-real.png) |
| 三态与降级 | [内容加载](ui-t22/16-content-loading.png)、[内容失败](ui-t22/17-content-error-injected.png)、[照片失败](ui-t22/18-photo-error-injected.png)、[新设备空页](ui-t22/19-my-empty.png)、[互动空页](ui-t22/20-messages-empty.png) |
| 中文场合标签 | [最终中文场合标签](ui-t22/26-outfit-chinese-labels.png) |
| 详情三态 | [互动加载](ui-t22/21-messages-loading.png)、[互动失败](ui-t22/22-messages-error-injected.png)、[积分加载](ui-t22/23-points-loading.png)、[积分失败](ui-t22/24-points-error-injected.png)、[清空后积分空页](ui-t22/25-points-empty-after-clear.png) |

## 文件范围与未做事项

- A8：models、009迁移、db、personal服务/路由、main、test_personal_api、test_db，定义协议和真实积分。
- B7：ootd服务/路由、main、wardrobe清空、personal、test_ootd_api、test_personal_clear，保存私密记录和可恢复清理。
- C：personal服务/路由、community作者名、3份新增内容/媒体/互动测试；审查后只读历史接口仍在原C文件中。
- D8：personalApi及测试、My、PersonalPhoto、App、BottomNav、Home、AppIcon，设备安全及入口。
- E8：Points、Messages、Settings、PersonalContent、OotdEditor、My、personalView、styles，页面与编辑。
- F：PostDetail、ProductDetail、personalView测试、My/styles；审查补丁复用已批准D/F文件。文档/新截图另计。

未新增注册登录、手机绑定/退出登录、邀请奖励、充值兑换、AI扣积分、个性化空开关、会员或备案信息；没有真实试穿/模型调用、云部署、隧道或GitHub同步。原本地求职材料保持忽略。当前仍是设备身份测试版，清浏览器存储会丢管理身份；正式法律文本、社区运营审核/存储治理、真实试穿资源与费用仍属原有边界。


## 备份与回滚（仅说明，未执行回滚）

实施前用SQLite backup复制数据库，并复制uploads和.quota_salt到本地忽略的data/t22-backup-*。应用数据仍使用原APP_DATA_DIR/default路径；未覆盖用户衣柜。需要撤回本轮时先停止前后端，再以功能前备份整组恢复app.db、uploads与.quota_salt，并切回功能前代码；不要单独复制一个旧库同时保留新uploads。

```bash
# 本机本轮功能前备份；先停服并另存当前数据。
backup_dir=data/t22-backup-20261120-112643
mv data/app.db data/app.before-rollback.db
mv data/uploads data/uploads.before-rollback
cp "$backup_dir/app.db" data/app.db
cp -R "$backup_dir/uploads" data/uploads
cp "$backup_dir/.quota_salt" data/.quota_salt
```

如使用APP_DATA_DIR，恢复目标路径相应改为该目录。没有DROP/DOWN迁移；不把删除新表当成无损回滚。回滚会回到备份时刻，之后产生的数据应事先另存。本轮没有执行这些破坏性恢复命令。


## 本地主分支收尾

已no-ff合入本地main；合并后重新执行make test/make lint：`409 passed in 5.27s`、`Tests 76 passed (76)`、`All checks passed!`、tsc退出0。现有本地后端/health回读`{"status":"ok"}`，没有停止用户原来的8000/5173开发服务；验收专用8022/5182/9227进程随后关闭。无远端Git更新。
