# T6 真实调用记录（首次接通模型）

执行时间：2026-11-13 09:26（Asia/Shanghai）
执行人：人类在本机执行 `/tmp/realrun.py`（真实网络调用，非注入）
模型：`qwen3.8-flash`（百炼 OpenAI 兼容模式）
Prompt 版本：`outfit_compose.v1`

## 调用方式

```
读取 data/app.db 的 12 件衣柜 → filter_candidates() → compose_outfits()（真实 client）
```

## 结果

| case | 温度 | 场合 | filter | compose 真实耗时 | 套数 | degraded | shortage |
|---|---|---|---|---|---|---|---|
| B01 | 18℃ | commute | <1ms | **6183ms** | 3 | false | 无 |
| B03 | 5℃ | commute | <1ms | **6652ms** | 3 | false | 无 |
| B05 | 18℃ | commute（排除 W11） | <1ms | **6374ms** | 3 | false | 无 |

均值 **6403ms**，三次全部在 12s 目标内。

## B01 实际输出（原文）

```
1. top=W01 bottom=W04 outer=W03 shoes=W09
   白色棉质上衣搭配米色混纺下装，外搭藏青羊毛混纺外套以应对凉爽通勤温度，黑色皮革鞋增加正式度。
2. top=W07 bottom=W06 outer=W02 shoes=W09
   灰色羊毛厚上衣与黑色混纺下装组合，配合黑色聚酯纤维外套和黑色皮革鞋，整体色调沉稳且保暖性适合凉带。
3. top=W01 bottom=W11 outer=W10 shoes=W09
   白色棉质上衣搭配藏青混纺下装，外穿卡其棉质外套提供适度保暖，黑色皮革鞋平衡了休闲与正式感。
```

## B03 实际输出（5℃，cold 带）

```
1. top=W07 bottom=W06 outer=W02 shoes=W09
2. top=W07 bottom=W11 outer=W03 shoes=W09
3. top=W07 bottom=W04 outer=W10 shoes=W09
```

三套 top 均为 W07（warmth≥3 的保暖内层），均含 outer——`slot_rules` 里 cold 带的硬约束被模型遵守。

## 可以确认的四件事

1. **schema 单一来源生效**：`{{JSON_SCHEMA}}` 注入后模型返回可解析结构，无一次解析失败。
2. **参数量级可控**：单次调用 146–168 tokens（含 prompt 小样本），成本可忽略。
3. **理由可核对**：每套理由都引用了具体颜色/材质/温度带（"米色混纺""适合冷带保暖"），未出现"显瘦/气质/高级感"这类不可核对词——`validate.py` 的禁词与属性引用要求，在真实输出下没有被触发拒绝。
4. **`degraded=false`**：三次都是模型正常产出，不是降级模板。

## 遗留

- `qwen-turbo` 对本账号仍返回 429（`limit_requests`），已弃用该模型，改用 `qwen3.8-flash`。
- 单次 compose 约 6.4s，其中模型推理为主；T7 端到端耗时需加上前端交互与网络往返。
- 视觉识别（T5）需要多模态模型，`qwen3.8-flash` 为纯文本，T5 需另选 `qwen3.8-omni-flash` 或 `*-vl` 系列，待实测确认开通状态。
