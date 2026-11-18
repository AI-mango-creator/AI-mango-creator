# T18 · 身材资料与衣橱分类验收

日期：2026-11-18。范围依次为A、B、C、D1、D2、E，D1/D2拆分已获批准；决策D11独立提交f0fa754。最终审查修复只涉及7个代码文件，文档/报告另计。

## 交付与边界

- 新增设备隔离的资料表及GET/PATCH `/api/profile`。身高cm、体重kg为用户填写的有限正数，可小数/留空；五体型X/A/TY/H/O由用户选择，均带SVG示意及原描述。资料来源为user；清空衣橱同时清除本设备资料。
- 有资料时使用编排v2，只供S3解释，不更改S2过滤；未填写沿用v1。资料不保证尺码或合身，页面说明会向现有模型发送资料；未写入模型日志。
- 十个分类入口（全部+九类），外套归上装、半身裙及连衣裙归裙装。管理分类`wardrobe_group`与搭配槽位`category`分开；未知项需用户归类和具体命名，上装/裙装明确搭配位置。套装/包包/首饰仅收纳，不能作为上装等核心槽位使用。
- 新识别v3按models生成JSON Schema，接受新增管理品类/unknown；旧v1/v2解析及录制仍保留。模型识别来源model，代码映射derived，人工修正user，未知仍须确认。

## 自动检查原始输出

命令：`zsh -ilc 'make test && make lint'`，exit 0。

```text
.venv/bin/python -m pytest -q app/tests
........................................................................ [ 21%]
........................................................................ [ 43%]
........................................................................ [ 65%]
........................................................................ [ 86%]
............................................                             [100%]
332 passed in 3.07s
cd web && npm test

> wardrobe-copilot-web@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/yuanying/Desktop/算法衣橱/web


 Test Files  6 passed (6)
      Tests  44 passed (44)
   Start at  08:59:12
   Duration  300ms (tests 72%, import 14%, transform 11%, worker 4%)

.venv/bin/python -m ruff check app
All checks passed!
cd web && npx tsc --noEmit
```

命令：`zsh -ilc 'cd web && npm run build'`，exit 0。

```text
> wardrobe-copilot-web@0.1.0 build
> tsc --noEmit && vite build

vite v7.3.8 building client environment for production...
transforming...
✓ 40 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.58 kB │ gzip:  0.40 kB
dist/assets/index-DlIH7369.css   14.63 kB │ gzip:  3.90 kB
dist/assets/App-C-kZQfcr.js      34.10 kB │ gzip: 10.99 kB
dist/assets/index-C0iYzw1V.js   144.86 kB │ gzip: 47.05 kB
✓ built in 392ms
```

各段全量结果：A316+34，B316+38，C319+38，D1/D2各329+38，E329+42；审查修复后332+44（pytest+Vitest），每段lint通过。迁移回放先暴露重复加列与人工分类覆盖，修复后新回归通过；既有表/owner/外键/数量断言保留。

## 375×812浏览器验收

Chrome CDP `Emulation.setDeviceMetricsOverride`：width375、height812、deviceScaleFactor1、mobile=true。临时APP_DATA_DIR数据库、端口18081，真实GET/PATCH与SQLite保存，三件衣物是明确的离线夹具，不计新增真实模型识别；错误由Chrome Fetch拦截注入503。未触及正式data/app.db。

| 截图 | 验证 |
|---|---|
| [01](ui-t18/01-wardrobe-all.png) | 三件夹具，十分类及计数 |
| [02](ui-t18/02-category-empty.png) | 首饰分类为空，有添加引导 |
| [03](ui-t18/03-classify-error-preserved.png) | 分类保存失败，输入及卡片保留 |
| [04](ui-t18/04-classified-top.png) | 真实PATCH成功，未知项进入上装，计数2 |
| [05](ui-t18/05-profile-loading.png) | 资料载入骨架 |
| [06](ui-t18/06-profile-empty.png) | 空资料引导 |
| [07](ui-t18/07-profile-save-error.png) | 保存失败，输入保留，可重试 |
| [08](ui-t18/08-profile-saved-bottom.png) | 保存成功，T/Y、H、O示意图及说明 |
| [09](ui-t18/09-profile-refreshed-top.png) | 刷新后165.5cm、55.2kg、A型保留，X/A示意图 |
| [10](ui-t18/10-device-changed-protected.png) | 设备切换后旧表单拒绝保存，B资料为空 |
| [11](ui-t18/11-profile-load-error.png) | 读取失败有重新加载入口，重试成功 |

原始浏览器记录：[t18-browser.json](t18-browser.json)。11张截图均innerWidth=375、scrollWidth=375、height=812；五型逐个选中返回X/A/TY/H/O；Runtime异常0。已实际复看分类失败与资料上下两段截图，五种轮廓可区分。

另外真实浏览器回归：外套改自定义名称“雨天防护服”，手选outer仍与原值相同。修复前保存遗漏category，结果null（RED）；修复后输出：

```text
PASS custom subtype preserves explicitly selected outer
```

## 审查及保护

独立只读审查发现资料请求跨设备、响应owner未校验、外套/连衣裙手工纠正残留旧槽位、未知单品通过旧category-only PATCH绕过具体命名，以及中止signal覆盖超时问题；均修复并跑全量检查。浏览器补检发现相同槽位选择漏传，亦已修复。

按`docs/reports/t5d-freeze.json`逐文件SHA256核对：

```text
frozen SHA256: 134/134 unchanged
```

原cases断言、原prompt v1/v2、134冻结证据不动。新prompt差异：编排v2只加资料用途与禁用合身推断说明；识别v3扩展套装/包/首饰/unknown及schema注入。未使用新测试结果替换旧模型评测数字。

迁移只增005表/006列。006重复运行检查既有列类型，仅回填NULL，不覆盖人工分类；其余迁移错误仍抛出。回退前应停服务并恢复迁移前完整数据目录备份，例如`cp -a data data.before-t18`（首次迁移前），需要回退时将当前目录另存，再`cp -a data.before-t18 data`，同时检出迁移前代码；不要用DROP删表删列，也不要用该命令覆盖仍运行的SQLite库。临时验收库不作为正式备份。

## 未验证与未做

新识别v3和带资料编排v2本轮未调用真实模型，新增类别识别质量/身材解释效果尚无真实评测；所有自动测试的模型响应均为明确注入。没有修改模型、增加依赖、扩展套装/包包/首饰推荐槽位，没有部署、开启分享链接、推送GitHub或更新飞书。T9/T14不在本轮范围。
