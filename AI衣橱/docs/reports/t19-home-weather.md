# T19 · 首页、真实天气与详情改版验收

日期：2026-11-18。设计及A→B→C分段已经人类批准，D2/D12先独立提交4e7149a。

## 改动与对应参考图

- 图1：浅粉渐变首页，档案/真实衣柜数量/天气入口，五个可用快捷入口、AI帮我搭横幅、个人衣物双列图墙、固定底部导航。
- 图2：七天日期胶囊、真实城市最低/最高温、中文天气及保暖建议、所选温度带入搭配。城市搜索多个同名结果由用户选择，不自动定位；不持久化位置。
- 图3：我的档案分区卡片、资料摘要与编辑，沿用用户输入身高cm/体重kg及五体型示意。没有增加人像/手部上传等数据。
- 图4：衣橱横分类计数、三列图片网格、导入衣橱与AI搭配固定操作；待确认、编辑、删除、失败保留仍可用。
- 底栏：首页/衣橱/搭配/我的，四个入口均有实际页面。用个人衣物替代参考商城商品，未增加社区、DIY、试穿、写真、日记或商品价格。

代码文件：
- A（6）：app/models.py、app/services/weather.py、app/routers/weather.py、app/main.py、app/tests/test_weather.py、app/tests/test_weather_api.py。
- B（8）：web/src/App.tsx、web/src/pages/Home.tsx、web/src/pages/Weather.tsx、web/src/components/BottomNav.tsx、web/src/components/AppIcon.tsx、web/src/lib/weatherApi.ts、web/src/lib/weatherApi.test.ts、web/src/styles.css。
- C（6）：web/src/pages/Profile.tsx、web/src/pages/Wardrobe.tsx、web/src/pages/Outfits.tsx、web/src/components/BodyShapeGuide.tsx、web/src/App.tsx、web/src/styles.css。
- 收尾修复（6）：weather.py、test_weather.py、test_weather_api.py、App.tsx、Profile.tsx、Home.tsx（标签改为我的衣物，不暗示收藏功能），均为已批准范围。

## 自动验收

命令：`zsh -ilc 'make test && make lint && cd web && npm run build'`，exit0。

```text
.venv/bin/python -m pytest -q app/tests
........................................................................ [ 20%]
........................................................................ [ 40%]
........................................................................ [ 60%]
........................................................................ [ 81%]
...................................................................      [100%]
355 passed in 3.54s
cd web && npm test

> wardrobe-copilot-web@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/yuanying/Desktop/算法衣橱/web


 Test Files  7 passed (7)
      Tests  50 passed (50)
   Start at  22:09:36
   Duration  310ms (tests 71%, import 13%, transform 11%, worker 4%)

.venv/bin/python -m ruff check app
All checks passed!
cd web && npx tsc --noEmit

> wardrobe-copilot-web@0.1.0 build
> tsc --noEmit && vite build

vite v7.3.8 building client environment for production...
transforming...
✓ 45 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.58 kB │ gzip:  0.40 kB
dist/assets/index-182WP_jy.css   28.56 kB │ gzip:  7.57 kB
dist/assets/App-CA_WCqiQ.js      51.47 kB │ gzip: 16.29 kB
dist/assets/index-BV_cY680.js   144.86 kB │ gzip: 47.05 kB
✓ built in 425ms
```

A最初22项天气测试因模块缺失RED，完成后354 pytest+44 Vitest、lint全绿；B6新增API/日期/取消测试先RED，完成后354+50、lint/build全绿；C354+50、lint/build全绿；最终总超时回归新增1条，355 passed in 3.17s、50 Vitest、lint及build425ms通过。既有332后端与44前端测试不删、不跳、不放宽。

## 独立审查与回归

发现并修复三项：
1. httpx2单阶段超时不能保证总8s，改为AsyncClient+asyncio.timeout(8)覆盖完整请求，路由仍在线程池同步调用；总deadline测试先RED后GREEN，测试只等待0.01s，不真睡8s。
2. 普通AI入口保留旧天气selection，改为只有天气页显式带入才保留，其他入口清空。浏览器修复前输出`FAIL ordinary AI entry reused weather selection: 15`；修复后`PASS ordinary AI entry uses manual default`。
3. 档案摘要读未保存草稿，改为独立已保存快照。浏览器修复前`FAIL unsaved draft leaks into overview`；修复后`PASS overview shows saved data after cancelling`。保存失败输入仍保留，返回摘要不伪称已保存。

## 真实天气验收（不含LLM）

固定Open-Meteo官方城市搜索/预报域名，无新依赖/账号，设备头不转发供应商。

正式后端实测原文：[t19-real-api.json](raw/weather/t19-real-api.json)。

| 请求 | HTTP | 服务端入口端到端耗时 | 结果 |
|---|---|---|---|
| 首次城市搜索深圳 | 504 | 8043ms | 总超时，中文提示，保留失败 |
| 七天预报22.55/114.1 | 200 | 1577ms | Asia/Shanghai、7天 |
| 人工再次搜索深圳 | 200 | 3845ms | 3个同名候选，未自动选第一项 |

浏览器另真实搜索城市→用户选择深圳广东→项目后端真实预报→所选最低温带入搭配，无Fetch注入、无模型调用。截图20/21标注真实天气，原始状态见[t19-real-browser.json](t19-real-browser.json)。当日展示18/28°C、毛毛雨，带入18°C（界面为四舍五入显示）。这是单次连通验收，不是天气准确率或可用性保证；初期TLS失败及上表504不隐去。

来源：[Open-Meteo预报](https://open-meteo.com/en/docs)、[城市搜索](https://open-meteo.com/en/docs/geocoding-api)、[非商业接口条款](https://open-meteo.com/en/terms)。页面有供应商署名与获取时间，失败可手填温度。

## 375×812浏览器验收

Chrome CDP `Emulation.setDeviceMetricsOverride` width375 height812 deviceScaleFactor1/mobile；不是window-size。

共27张图全部innerWidth375、height812、scrollWidth375，Runtime异常0。已实际复看首页/三列衣橱/档案/真实天气与温度带入/上传失败/天气失败。底栏固定，正文为其预留空间；分类与日期只在自己的容器内滚动。

除20/21两张真实天气外，天气成功/失败及编排状态由浏览器Fetch明确注入，截图顶部均标注；衣柜/档案使用隔离临时SQLite的真实GET/PATCH。该库14件基准衣物配测试照片仅用于布局，不是本轮识别结果，不声称图与属性准确对应；未触碰正式衣柜。

- 首页loading/empty/error/有衣物、天气empty/loading/候选/成功/error、衣橱loading/empty/error/三列、档案loading/读取错误/摘要/编辑/保存失败、搭配loading/缺件/error/基础方案与可关闭黄条均实际检查。
- 上传超时注入后，File仍1个，原地重试两次捕获FormData的draft_id相同（非空），照片占位和中文错误保留；没有真实调用视觉模型。
- 档案实际保存173.5cm后读取摘要正确；保存失败177cm仍在输入框，取消后摘要仍为173.5cm。
- 搭配黄条关闭后消失；临时库sessions为0，所有编排展示均明确为UI注入，未制造新真实模型证据。

原始记录：[主流程](t19-browser.json)、[空错与上传](t19-browser-states.json)、[页面错误](t19-browser-errors.json)、[真实天气](t19-real-browser.json)。

| 截图 | 视口 | scrollWidth |
|---|---|---|
| [01-home](ui-t19/01-home.png) | 375×812 | 375 |
| [02-wardrobe](ui-t19/02-wardrobe.png) | 375×812 | 375 |
| [03-profile](ui-t19/03-profile.png) | 375×812 | 375 |
| [04-profile-edit](ui-t19/04-profile-edit.png) | 375×812 | 375 |
| [05-weather-empty](ui-t19/05-weather-empty.png) | 375×812 | 375 |
| [06-city-search](ui-t19/06-city-search.png) | 375×812 | 375 |
| [07-weather-loading](ui-t19/07-weather-loading.png) | 375×812 | 375 |
| [08-weather](ui-t19/08-weather.png) | 375×812 | 375 |
| [09-outfits-weather](ui-t19/09-outfits-weather.png) | 375×812 | 375 |
| [10-outfits-loading](ui-t19/10-outfits-loading.png) | 375×812 | 375 |
| [11-outfits-shortage](ui-t19/11-outfits-shortage.png) | 375×812 | 375 |
| [12-home-loading](ui-t19/12-home-loading.png) | 375×812 | 375 |
| [13-home-empty](ui-t19/13-home-empty.png) | 375×812 | 375 |
| [14-wardrobe-empty](ui-t19/14-wardrobe-empty.png) | 375×812 | 375 |
| [15-home-error](ui-t19/15-home-error.png) | 375×812 | 375 |
| [16-profile-error](ui-t19/16-profile-error.png) | 375×812 | 375 |
| [17-upload-error-preserved](ui-t19/17-upload-error-preserved.png) | 375×812 | 375 |
| [18-delete-confirm](ui-t19/18-delete-confirm.png) | 375×812 | 375 |
| [19-outfits-degraded](ui-t19/19-outfits-degraded.png) | 375×812 | 375 |
| [20-weather-real](ui-t19/20-weather-real.png) | 375×812 | 375 |
| [21-outfits-real-weather](ui-t19/21-outfits-real-weather.png) | 375×812 | 375 |
| [22-weather-error](ui-t19/22-weather-error.png) | 375×812 | 375 |
| [23-wardrobe-loading](ui-t19/23-wardrobe-loading.png) | 375×812 | 375 |
| [24-wardrobe-error](ui-t19/24-wardrobe-error.png) | 375×812 | 375 |
| [25-profile-loading](ui-t19/25-profile-loading.png) | 375×812 | 375 |
| [26-profile-load-error](ui-t19/26-profile-load-error.png) | 375×812 | 375 |
| [27-outfits-error](ui-t19/27-outfits-error.png) | 375×812 | 375 |

## 保护与未做

```text
frozen 134/134 unchanged
QA model sessions 0
```

未改prompt/cases/冻结证据、模型、依赖、数据库结构；天气协议只追加models，不修改已有衣物或资料字段。未重新做真实上传/模型编排评测，旧真实模型指标沿用旧报告；未做试穿/商城/社区/GPS/位置持久化。免费天气服务确有一次超时，网络失败会明确提示并允许手填；位置刷新后重新选择。

本轮按授权合入本地main，不自动同步GitHub或开启临时通道。当前本地5173根页200、8000天气无设备头400已复核，刷新页面即可查看改版。
