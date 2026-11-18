# T19 首页天气改版 Implementation Plan

> For agentic workers: 使用superpowers:executing-plans，在当前任务分支自行顺序实施；用户已批准A→B→C连续执行，不重复索要确认。

Goal：还原参考四图的粉色首页/天气/档案/三列衣橱并保留真实业务。
Architecture：既有API+App页面状态；天气固定Open-Meteo域名，models为协议真相，未知/失败不伪造数据。
Tech Stack：现有React18/TS/Tailwind/FastAPI/Pydantic/httpx2，无新依赖。
Spec：docs/superpowers/specs/2026-11-18-home-weather-design.md（人类已批准）。

## Global Constraints
- A6/B8/C≤6文件；docs/reports另计，先独立提交D2/D12。
- 不改旧测试断言/prompt/cases/134冻结项；临时库与传输层注入，不调用真实LLM。
- 每段全量test/lint→提交→下一段；最终CDP375×812和真实天气联网。

## Review Focus
- 城市切换竞态/跨午夜/7天不齐及非法经纬度：A协议测试，B API校验与过期判断。
- 天气失败不阻塞衣橱/手填温度：B独立状态、C手工入口，浏览器注入。
- 档案保存/设备切换保护与衣橱待确认/上传失败保留：C复用现有逻辑，临时库浏览器检查。
- 底部导航遮挡/三列图片失败/横向溢出：C图片组件复用、CDP数据与截图。

## A 天气后端（6）
models.py、services/weather.py、routers/weather.py、main.py、tests/test_weather.py、tests/test_weather_api.py。
接口search_cities(q,transport=None)->WeatherCities；forecast(lat,lon,transport=None)->WeatherForecast；weather_text(code)及温度提示。固定8s超时，不重试/缓存；上游schema严格校验，范围/日期/并行数组不能缺失。
- [x] 先新增测试（路由404/模块缺失RED）：200城市/空集/7天/上游超时504坏响应502/参数400/设备400/温度带规则。
- [x] 实现协议/HTTP固定域名/路由；只GET外部天气、不读取密钥或转发设备ID。
- [x] 全量make test/lint，记录实测再提交。

## B 首页与天气/导航（8）
App.tsx、pages/Home.tsx、pages/Weather.tsx、components/BottomNav.tsx、components/AppIcon.tsx、lib/weatherApi.ts、lib/weatherApi.test.ts、styles.css。
weatherApi导出searchCities/getWeather/forecastTemperature/forecastIsFresh，协议字段与A一致。App保留city/forecast/selectedDate状态；Home接loadWardrobe/getProfile与真实天气，BottomNav仅首页/衣橱/搭配/我的。Weather城市搜索与选择、七天卡、独立loading/error/empty及重试，过期不预填。
- [x] API/日期/负数四舍五入/过期/设备头/错误/取消测试RED。
- [x] 实现API、图标、导航、首页与天气页；保留现有三页入口，城市状态本轮不持久化。
- [x] 全量test/lint/build，记录实测再提交。

## C 详情视觉与接线（≤6）
pages/Profile.tsx、pages/Wardrobe.tsx、pages/Outfits.tsx、components/BodyShapeGuide.tsx、App.tsx、styles.css。
Profile摘要+编辑；Wardrobe横分类/三列网格/上传与AI底操作；Outfits可接initialWeather={temperature,city,date}并显示来源，温度仍可改；底部统一留足空间。现有请求/确认/上传/删除/降级逻辑不另写。
- [x] 不为样式写镜像单测；功能沿用已有测试，先用浏览器确认旧版布局缺失作为RED记录。
- [x] 实现视觉和props接线；全量test/lint/build。
- [x] 独立whole-branch只读审查、一次修复并回归；CDP375×812多态截图/真实天气验证/冻结检查。
- [x] 回填tasks/CHANGELOG/报告，按授权no-ff合main；不发布GitHub，不开通道。

## Ledger
- 2026-11-18 已批准连续A/B/C。天气探针城市搜索200、forecast TLS失败；这是未完成的验收，不作为已连通。

- A complete：354 pytest+44 Vitest、lint通过，6代码文件，无旧断言变更。城市搜索200/forecast TLS失败待真实验收。

- B complete：354 pytest+50 Vitest，lint/build通过，8代码文件；页面时钟每30s重算过期，独立天气状态不阻塞衣橱。上传/天气温度的跨页接线由C完成。

- Final：独立审查3项已修复（backend总deadline、普通入口selection、资料草稿）；1新增deadline测试，355+50/lint/build425ms全绿。浏览器27张375×812全通过，真实城市搜索/预报/带入通过；保留城市首个504及预检TLS失败。134冻结项不变，无LLM调用。
