import json
import re
from collections.abc import Sequence
from itertools import chain, combinations, product
from pathlib import Path

from app.models import STORAGE_ONLY_GROUPS, Occasion, WardrobeItem

_SPEC = json.loads(
    (Path(__file__).resolve().parents[2] / "cases" / "cases.json").read_text(encoding="utf-8")
)["meta"]["filter_spec"]
_SLOT_LABELS = {
    "top": "上装", "bottom": "下装", "outer": "外套", "shoes": "鞋",
    "dress": "连衣裙", "accessory": "配饰",
}


def _temperature_interval(expression: str) -> tuple[int | None, int | None]:
    comparison = re.match(r"(>=|<=|>|<)(-?\d+)\Z", expression)
    if comparison:
        operator, number = comparison.groups()
        bound = int(number)
        if operator == ">=":
            return bound, None
        if operator == ">":
            return bound + 1, None
        if operator == "<=":
            return None, bound
        return None, bound - 1
    interval = re.match(r"(-?\d+)-(-?\d+)\Z", expression)
    if interval:
        return tuple(int(value) for value in interval.groups())
    raise ValueError("温度带规则格式无法识别。")


def _overlaps(left, right) -> bool:
    lower = [value for value in (left[0], right[0]) if value is not None]
    upper = [value for value in (left[1], right[1]) if value is not None]
    return not lower or not upper or max(lower) <= min(upper)


def _slot_rules() -> dict:
    text = "\n".join(_SPEC["slot_rules"])
    patterns = {
        "base": r"每套必含 ([a-z+ ]+)（([a-z]+) 可替代 ([a-z+]+)）",
        "required_outer": r"band in \(([^)]+)\) 时必含 ([a-z]+)",
        "forbidden_outer": r"band in \(([^)]+)\) 时 ([a-z]+) 不出现",
        "inner": r"band==([a-z]+) 时 ([a-z]+)\.warmth >= (\d+)",
        "capacity": r"每个 slot 只能 (\d+) 件",
    }
    matches = {name: re.search(pattern, text) for name, pattern in patterns.items()}
    if not all(matches.values()) or "单品不得在 excluded 列表内" not in text:
        raise ValueError("槽位规则格式无法识别，请核对过滤规则。")
    base, alternative, replaced = matches["base"].groups()
    required_bands, outer = matches["required_outer"].groups()
    forbidden_bands, forbidden_outer = matches["forbidden_outer"].groups()
    inner_band, inner_slot, inner_warmth = matches["inner"].groups()
    if outer != forbidden_outer:
        raise ValueError("外套槽位规则不一致。")
    return {
        "base": tuple(slot.strip() for slot in base.split("+")),
        "alternative": alternative,
        "replaced": tuple(replaced.split("+")),
        "outer": outer,
        "required_outer_bands": tuple(band.strip() for band in required_bands.split(",")),
        "forbidden_outer_bands": tuple(band.strip() for band in forbidden_bands.split(",")),
        "inner_band": inner_band,
        "inner_slot": inner_slot,
        "inner_warmth": int(inner_warmth),
        "capacity": int(matches["capacity"].group(1)),
    }


_BANDS = {name: _temperature_interval(value) for name, value in _SPEC["band_by_temp"].items()}
_SLOTS = _slot_rules()
# 鞋这类槽位不存在"保暖等级"语义：夏天能否穿一双鞋由 seasons 决定，不由 warmth 决定。
# 名单来自 filter_spec，代码不自行发明槽位。
_WARMTH_EXEMPT = frozenset(_SPEC.get("warmth_exempt_slots", ()))


def temperature_band(temp_c: int) -> str:
    if isinstance(temp_c, bool) or not isinstance(temp_c, int):
        raise TypeError("温度必须是整数。")
    matches = [band for band, interval in _BANDS.items() if _overlaps((temp_c, temp_c), interval)]
    if len(matches) != 1:
        raise ValueError("温度带规则存在重叠或未覆盖当前温度。")
    return matches[0]


def _warmth_min(slot: str, band: str) -> int:
    lower = _SPEC["allowed_warmth"][band][0]
    inner_slots = {_SLOTS["inner_slot"]}
    if _SLOTS["inner_slot"] in _SLOTS["replaced"]:
        inner_slots.add(_SLOTS["alternative"])
    if band == _SLOTS["inner_band"] and slot in inner_slots:
        return max(lower, _SLOTS["inner_warmth"])
    return lower


def _warmth_allowed(item: WardrobeItem, band: str) -> bool:
    if item.category in _WARMTH_EXEMPT:
        return True
    return item.warmth is not None and _overlaps(
        (item.warmth, item.warmth), _SPEC["allowed_warmth"][band]
    )


def _allowed_slot(item: WardrobeItem, band: str) -> bool:
    if item.wardrobe_group in STORAGE_ONLY_GROUPS:
        return False
    if item.category is None:
        return False
    if item.category == _SLOTS["outer"] and band in _SLOTS["forbidden_outer_bands"]:
        return False
    if item.category in _WARMTH_EXEMPT:
        return True
    return item.warmth is not None and item.warmth >= _warmth_min(item.category, band)


def _slot_plans(band: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if band not in _BANDS:
        raise ValueError("温度带不存在。")
    required = list(_SLOTS["base"])
    if band in _SLOTS["required_outer_bands"]:
        required.append(_SLOTS["outer"])
    alternative = [slot for slot in required if slot not in _SLOTS["replaced"]]
    alternative.append(_SLOTS["alternative"])
    return tuple(required), tuple(alternative)


def _by_slot(candidates: Sequence[WardrobeItem], band: str) -> dict[str, list[str]]:
    groups = {}
    for item in {item.id: item for item in candidates}.values():
        if _allowed_slot(item, band):
            groups.setdefault(item.category, []).append(item.id)
    return groups


def count_composable_sets(candidates: Sequence[WardrobeItem], band: str) -> int:
    """穷举完整组合的不同单品 ID 集；不读文件、不写状态。"""
    plans = _slot_plans(band)
    groups = _by_slot(candidates, band)
    unique_sets = set()
    for plan in plans:
        options = [tuple(combinations(groups.get(slot, ()), _SLOTS["capacity"])) for slot in plan]
        for selection in product(*options):
            ids = tuple(chain.from_iterable(selection))
            if len(set(ids)) == len(ids):
                unique_sets.add(frozenset(ids))
    return len(unique_sets)


def filter_candidates(
    wardrobe: Sequence[WardrobeItem], *, temp_c: int, occasion: Occasion,
    excluded: Sequence[str] = (), formality_target: Sequence[int] | None = None,
    wardrobe_override: Sequence[str] | None = None,
) -> dict:
    band = temperature_band(temp_c)
    target = formality_target if formality_target is not None else _SPEC["occasion_formality"].get(occasion)
    if target is None or len(target) != 2 or target[0] > target[1]:
        raise ValueError("场合或正式度区间无效。")
    override = set(wardrobe_override) if wardrobe_override is not None else None
    excluded_ids = set(excluded)
    candidates = [
        item for item in {item.id: item for item in wardrobe}.values()
        if (override is None or item.id in override) and item.id not in excluded_ids
        and not item.needs_confirm and _allowed_slot(item, band)
        and _warmth_allowed(item, band)
        and item.formality is not None and _overlaps((item.formality, item.formality), target)
        and set(item.seasons) & set(_SPEC["allowed_seasons"][band])
    ]
    count = count_composable_sets(candidates, band)
    shortage = None
    if not count:
        groups = _by_slot(candidates, band)
        alternatives = [
            [slot for slot in plan if len(groups.get(slot, ())) < _SLOTS["capacity"]]
            for plan in _slot_plans(band)
        ]
        missing = min(alternatives, key=len)
        shortage = {
            "missing_slots": missing,
            "requirements": [
                {"slot": slot, "warmth_min": _warmth_min(slot, band), "formality_min": target[0]}
                for slot in missing
            ],
            "message": "没有完整搭配，缺少符合条件的单品：" + "、".join(_SLOT_LABELS[slot] for slot in missing),
        }
    return {"band": band, "candidates": candidates, "composable_count": count, "shortage": shortage}
