# 真实模型服务错误样本（用于 T8 夹具与失败处理证据）

采集时间：2026-11-13 09:06–09:12（Asia/Shanghai）
采集方式：`curl` 直调 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
账号状态：个人实名认证于 2026-11-13 完成；百炼模型服务**尚未开通**

这些是**真实返回**，不是构造的。T8 的错误分类测试直接引用本文件的响应体作为夹具，
不要另写一份编造的 JSON。

---

## 1) 429 · 限流（qwen-turbo）

```json
{"error":{"message":"You have exceeded your current request limit. For details, see: https://help.aliyun.com/zh/model-studio/error-code#rate-limit","type":"limit_requests","param":null,"code":"limit_requests"},"request_id":"a3bbd900-697f-901f-9b1d-c0c3673d2659"}
```

HTTP 状态 429，耗时约 1.7s。
含义：该模型对本账号可见，但当前请求配额不足（QPS/额度为 0）。
工程处理：等待 5s 重试 1 次（计入 D7.1 预算），仍 429 → 规则模板降级，`degrade_reason=rate_limit`。

**持续性证据**：同一模型从 2026-11-12 23:36 到 2026-11-13 09:12 连续多轮均返回 429，
跨越 10 小时以上，可排除"瞬时抖动"。这不是超时，不能按超时处理（超时不重试，429 要重试 1 次）。

## 2) 403 · 未开通（qwen-plus / qwen-flash / qwen3.8-flash / qwen3.7-flash / deepseek-v4.1-flash）

```json
{"error":{"code":"AccessDenied.Unpurchased","message":"Access to model denied. Please make sure you are eligible for using the model.","type":"access_denied","request_id":"..."}}
```

HTTP 状态 403，耗时约 1.6–1.8s。
含义：模型未在百炼控制台开通（不是 key 无效——key 无效会是 401）。
工程处理：**不重试**，直接判为配置错误，文案"AI 服务暂不可用"，并记录可运维的日志。

## 3) 模型目录可读、调用被拒（对照证据）

同一 key 请求 `GET /compatible-mode/v1/models` 返回 200、共 182 个模型 id。
说明：**认证链路是通的**，`/models` 返回的是模型广场目录，不代表本账号已获授权。
因此"能列出模型"不能作为"能调用模型"的证据——以后排查时先看 `/chat/completions` 的状态码。

---

## 三类错误的处理约定（对应 T8）

| 状态 | 分类 | 是否重试 | 用户可见 | 降级产物 |
|---|---|---|---|---|
| 401 | `auth` | 否 | "AI 服务暂不可用，请稍后再试" | 规则模板 3 套，`degraded=true` |
| 403 | `auth`（未授权/未开通） | 否 | 同上 | 同上 |
| 429 | `rate_limit` | 是，等待 5s，最多 1 次 | 黄条"AI 正忙，已为你用基础规则搭配" | 规则模板 3 套 |
| 超时 >20s | `timeout` | 否 | 黄条"AI 响应超时，已为你用基础规则搭配" | 规则模板 3 套 |
| 非 JSON / schema 不符 | `parse` | 是，1 次（带失败原因） | 同上 | 规则模板 3 套 |

降级产物必须仍通过 `validate.py`：候选集外单品、槽位重复、套内重复一律拒绝。
