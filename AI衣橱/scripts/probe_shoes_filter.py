"""实证：新增两双真实鞋后，各温度带的候选集与组合数如何变化。
重点验证：模型给 shoe1 判 warmth=3，会不会在 hot 带被误杀。
"""
from pathlib import Path

from app.models import SeedData, WardrobeItem
from app.services.filter import filter_candidates, temperature_band

data = SeedData.model_validate_json(Path("cases/cases.json").read_text(encoding="utf-8"))
base = list(data.wardrobe)

# 两双鞋的识别结果（qwen3.8-omni-flash 真实返回，2026-11-13）
shoe1 = WardrobeItem(
    id="shoe1_aj1low", name="拼色板鞋", category="shoes", sub="运动鞋",
    colors=["白色", "黑色", "卡其色"], material="皮革", pattern="纯色",
    warmth=3, formality=1, seasons=["spring", "summer", "autumn", "winter"],
    confidence=0.98,
)
shoe2 = WardrobeItem(
    id="shoe2_zoomx", name="复古跑鞋", category="shoes", sub="运动鞋",
    colors=["白色", "灰色"], material="网面麂皮拼接", pattern="纯色",
    warmth=2, formality=1, seasons=["spring", "summer", "autumn"],
    confidence=0.95,
)

print("=" * 62)
print("场景 A：现有 12 件基准衣柜")
print("=" * 62)
for temp in [28, 22, 18, 8]:
    r = filter_candidates(base, temp_c=temp, occasion="weekend")
    ids = [c.id for c in r["candidates"]]
    print(f"{temp:>2}℃ band={temperature_band(temp):<5} 候选={len(ids):>2} 组合={r['composable_count']:>3} 缺件={r['shortage']}")

print()
print("=" * 62)
print("场景 B：基准衣柜 + 2 双真实鞋（共 14 件）")
print("=" * 62)
full = base + [shoe1, shoe2]
for temp in [28, 22, 18, 8]:
    r = filter_candidates(full, temp_c=temp, occasion="weekend")
    ids = [c.id for c in r["candidates"]]
    shoes = sorted(c.id for c in r["candidates"] if c.category == "shoes")
    s1 = "✓" if "shoe1_aj1low" in ids else "✗被过滤"
    s2 = "✓" if "shoe2_zoomx" in ids else "✗被过滤"
    print(f"{temp:>2}℃ band={temperature_band(temp):<5} 候选={len(ids):>2} 组合={r['composable_count']:>3} "
          f"| shoe1(warmth3)={s1:<8} shoe2(warmth2)={s2:<8} | 鞋候选={shoes}")

print()
print("=" * 62)
print("场景 C：只把 warmth 改成 2，其余不变（验证归因）")
print("=" * 62)
shoe1_fixed = shoe1.model_copy(update={"warmth": 2})
for temp in [28, 18]:
    r = filter_candidates(base + [shoe1_fixed, shoe2], temp_c=temp, occasion="weekend")
    ids = [c.id for c in r["candidates"]]
    print(f"{temp:>2}℃ shoe1(warmth2)={'✓在候选中' if 'shoe1_aj1low' in ids else '✗仍被过滤'} 组合={r['composable_count']}")
