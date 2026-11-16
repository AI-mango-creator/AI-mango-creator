# T15 删除与方案图片预览

本轮范围已批准：七个代码文件，文档与新截图另计。T15基于main的c776b9d，未夹带T14；D10-c先行单独提交86a4e07。

## 实施与验收计划

- 后端：先在现有test_wardrobe_api.py追加临时库测试，验证204/重复404/跨owner404、历史引用与空方案清理、共用照片最后引用删除、文件失败回滚、越界拒绝；看到RED后修改wardrobe路由。不改表、模型或响应结构。
- 前端：api.test.ts追加删除204与失败保留、照片带设备头/取消/释放ObjectURL的测试；api.ts支持无body响应与照片资源生命周期。共用ItemPhoto组件覆盖loading、成功、无照片与请求/解码失败，不显示裂图。Wardrobe加二次确认和删除按钮；Outfits按slots映射items展示缩略图并保留理由。
- 浏览器：375×812使用CDP设备模拟，截图正常/加载中/图裂降级及删除确认/处理中/失败保留/成功移除；明确记录测试注入，不冒充新一次真实模型验收。
- 完成后make test、make lint、前端build，核对七文件范围与134冻结文件；回填任务板和CHANGELOG，提交并按约定--no-ff合入main。

## 结果

实现与本轮验收通过，T15✅，等待人类复核；T14仍在独立分支待Docker验收。

## 测试与构建原文

```text
$ .venv/bin/python -m pytest -q app/tests/test_wardrobe_api.py -k 'test_delete_'
4 passed, 49 deselected in 0.19s

$ zsh -ilc 'make test'
283 passed in 2.55s
Test Files  4 passed (4)
Tests  34 passed (34)

$ zsh -ilc 'make lint'
.venv/bin/python -m ruff check app
All checks passed!
cd web && npx tsc --noEmit

$ zsh -ilc 'cd web && npm run build'
vite v7.3.8 building client environment for production...
✓ 36 modules transformed.
✓ built in 367ms
```

上述命令exit0。后端新增4条先RED（405而非204/404/500），再实现转绿；前端新增5条先RED（删除/照片生命周期方法缺失），再实现转绿。基线main为279 pytest+29 Vitest；T14新增的10条测试在独立分支，本轮没有删除或跳过它们。既有测试函数/断言未更改，仅在批准的两个测试文件新增用例。

独立只读审查未发现阻断问题，审查实际执行`pytest -q app/tests/test_wardrobe_api.py -k delete`→`4 passed, 49 deselected in 0.18s`。

## 375×812浏览器验收

Chrome真实无头浏览器，**CDP Emulation.setDeviceMetricsOverride**设375×812、scale1；未用--window-size充当375视口。七张均已逐张查看，innerWidth=scrollWidth=375、height812、brokenImages=0；Runtime异常0。原始请求/尺寸/资源与数据库断言见[t15-browser.json](t15-browser.json)。

| 截图 | 检查结果 |
|---|---|
| [正常预览](ui-t15/01-previews-normal.png) | 三列按上装/下装/鞋排列，照片、槽位、品类子类和颜色可读，原理由保留 |
| [图片加载中](ui-t15/02-previews-loading.png) | 暂挂照片响应，九张显示加载占位，方案与理由不丢失 |
| [图片损坏降级](ui-t15/03-previews-image-error.png) | 注入image/jpeg但无法解码的字节，九张均转品类·子类文字块，零裂图 |
| [删除确认](ui-t15/04-delete-confirm.png) | 原文“删除后将从历史方案中移除，不可恢复”，删除入口与弹层375px未挤出 |
| [删除等待](ui-t15/05-delete-pending.png) | 暂挂DELETE，确认按钮显示正在删除且禁用，卡片保留 |
| [失败保留](ui-t15/06-delete-error-preserved.png) | 注入500中文错误，卡片/23件计数保留，可原地重试 |
| [删除成功](ui-t15/07-delete-success.png) | 恢复真实DELETE，返回204，卡片墙与临时库23→22，成功提示可见 |

**证据边界**：本次以只读SQLite backup和照片副本创建隔离临时环境（后端18015，前端5175）。原衣柜及照片不执行删除，不占模型额度。编排仍走过滤→generate_outfits→client.chat，但只在验收进程的client传输层注入合法响应；截图顶部显式标“验收：编排离线注入 · 图片/删除走临时库”。图片请求、最终成功DELETE与数据库落地是真接口；延迟、损坏图片和500为CDP故障注入。产品默认路径没有mock开关。**本报告不宣称新增真实模型调用通过。**

## 删除与资源断言

```text
failure_preserved: true
success_removed_from_database: true
repeated_delete_status: 404
final_urls: {"made":27,"revoked":27,"active":0}
runtime_errors: []
sqlite_after_delete:
{"wardrobe_remaining":22,"deleted_item_rows":0,"deleted_item_references":0,
 "foreign_key_violations":[],"last_reference_photo_exists":false}
```

单测另验证：删除共用照片的第一件后文件仍在，最后一件删除后文件消失；删除引用后仍有单品的方案保留、空方案清理、session保留；跨owner与不存在均404；unlink权限错误回滚单品删除并保留图片；照片路径越界至其他owner时拒绝且不删记录/文件。

前端在成功后才移除当前卡片，迟到的旧GET通过已删ID集合过滤，避免复活卡片；失败不清用户输入。ObjectURL在组件卸载、取消或解码失败时释放，迟到响应不能再创建URL。

## 范围与未做事项

- 七个代码文件，未改models响应结构、数据库schema、依赖或软删标记。
- 不改prompt、cases断言和134项冻结证据；仅新增本轮报告与截图。
- 未实现T9、未调用真实模型、未联网评测、未部署；T14容器验收仍未执行。
- 本轮正常预览取自已存在的真实照片；未把这次UI测试计入识别准确率或端到端模型耗时。
