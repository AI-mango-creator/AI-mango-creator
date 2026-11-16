from collections.abc import Sequence
from itertools import product

from app.llm.errors import FallbackValidationError
from app.models import (
    DRESS_SLOTS,
    OUTER_BANDS,
    STANDARD_SLOTS,
    ComposeResult,
    Composition,
    DegradeReason,
    OutfitSlots,
    ProposedOutfit,
    Slot,
    WardrobeItem,
)
from app.services.filter import count_composable_sets
from app.services.validate import validate_outfits


def _template_composition(candidates: Sequence[WardrobeItem], band: str) -> Composition:
    outer = {Slot.OUTER} if band in OUTER_BANDS else set()
    by_id = {item.id: item for item in candidates}
    groups = {slot: sorted((item for item in by_id.values() if item.category == slot.value),
                           key=lambda item: item.id) for slot in Slot}
    combinations = {}
    for plan in (STANDARD_SLOTS | outer, DRESS_SLOTS | outer):
        slots = sorted(plan, key=lambda slot: slot.value)
        for selection in product(*(groups[slot] for slot in slots)):
            if len({item.id for item in selection}) != len(selection):
                continue
            if count_composable_sets(selection, band) != 1:
                continue
            identity = tuple(sorted(item.id for item in selection))
            combinations[identity] = {slot.value: item.id for slot, item in zip(slots, selection)}
    if not combinations:
        raise FallbackValidationError(["候选集无法组成合规基础搭配。"])
    selected = []
    used = set()
    strategies = (
        ("按正式度从高到低搭配", "formality", -1),
        ("按舒适策略（正式度从低到高）搭配", "formality", 1),
        ("按厚薄从高到低搭配", "warmth", -1),
    )
    for label, attribute, direction in strategies:
        ranked = sorted(combinations, key=lambda ids: (
            direction * sum(getattr(by_id[item_id], attribute) or 0 for item_id in ids), ids,
        ))
        identity = next((ids for ids in ranked if ids not in used), None)
        if identity is None:
            break
        used.add(identity)
        slots = dict.fromkeys(OutfitSlots.model_fields) | combinations[identity]
        reference = by_id[identity[0]]
        color = reference.colors[0] if reference.colors else "未标注颜色"
        reason = f"{label}：{reference.id}为{color}、厚薄{reference.warmth}、正式度{reference.formality}。"
        selected.append(ProposedOutfit(slots=OutfitSlots.model_validate(slots), reason=reason))
    return Composition(sets=selected)


def fallback_outfits(
    candidates: Sequence[WardrobeItem], *, band: str, degrade_reason: DegradeReason,
) -> ComposeResult:
    """仅从原候选集构造派生结果；模板产物必须再次通过原 S4。"""
    composition = _template_composition(candidates, band)
    expected_count = min(3, count_composable_sets(candidates, band))
    failures = validate_outfits(composition, candidates, band=band, expected_count=expected_count)
    if failures:
        raise FallbackValidationError(failures)
    return ComposeResult(
        sets=composition.sets, degraded=True, degrade_reason=degrade_reason,
        shortage_hint=f"符合条件的不同基础搭配仅 {expected_count} 套。" if expected_count < 3 else None,
    )
