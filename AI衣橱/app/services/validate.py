from collections.abc import Sequence

from app.models import (
    DRESS_SLOTS,
    OUTER_BANDS,
    STANDARD_SLOTS,
    Composition,
    Slot,
    WardrobeItem,
)
from app.services.filter import count_composable_sets

_UNVERIFIABLE = ("显瘦", "气质", "高级感", "百搭神器")


def validate_outfits(
    composition: Composition, candidates: Sequence[WardrobeItem], *,
    band: str, expected_count: int,
) -> list[str]:
    """S4 只返回可反馈的规则错误；不联网、不改候选及模型来源。"""
    errors = []
    allowed = {item.id: item for item in candidates}
    if len(composition.sets) != expected_count:
        errors.append(f"方案数量必须为 {expected_count} 套。")
    seen = set()
    for index, outfit in enumerate(composition.sets, 1):
        prefix = f"第 {index} 套："
        slots = {Slot(key): value for key, value in outfit.slots.model_dump().items() if value is not None}
        ids = list(slots.values())
        if len(ids) != len(set(ids)):
            errors.append(prefix + "同套存在重复单品。")
        identity = frozenset(ids)
        if identity in seen:
            errors.append(prefix + "重复方案不能用于凑数。")
        seen.add(identity)
        outer = {Slot.OUTER} if band in OUTER_BANDS else set()
        plans = (STANDARD_SLOTS | outer, DRESS_SLOTS | outer)
        if set(slots) not in plans:
            errors.append(prefix + "槽位不完整或含当前温度带禁用的槽位。")
        selected = []
        for slot, item_id in slots.items():
            item = allowed.get(item_id)
            if item is None:
                errors.append(prefix + f"单品 {item_id} 不在候选集内。")
            elif item.category != slot.value:
                errors.append(prefix + f"单品 {item_id} 与槽位 {slot.value} 不符（可能重复品类）。")
            else:
                selected.append(item)
        if selected and count_composable_sets(selected, band) != 1:
            errors.append(prefix + "所选单品无法组成符合温度和保暖规则的完整方案。")
        if any(word in outfit.reason for word in _UNVERIFIABLE):
            errors.append(prefix + "理由包含不可核对的词。")
        facts = [fact for item in selected for fact in (
            *item.colors, item.material, f"厚薄{item.warmth}", f"正式度{item.formality}",
        ) if fact]
        if not any(fact in outfit.reason for fact in facts):
            errors.append(prefix + "理由必须引用所选单品的真实属性（颜色、材质、厚薄或正式度）。")
    return errors
