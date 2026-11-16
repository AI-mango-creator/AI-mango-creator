import json
from pathlib import Path

import pytest

from app.models import WardrobeItem
from app.services.filter import (
    count_composable_sets,
    filter_candidates,
    temperature_band,
)

DATA = json.loads((Path(__file__).resolve().parents[2] / "cases" / "cases.json").read_text())
SPEC = DATA["meta"]["filter_spec"]
CASES = {
    case["id"]: case for case in DATA["cases"]
    if case["id"].startswith("B") or case["id"] in {"C01", "C02"}
}
FILTER_KEYS = {"temp_c", "occasion", "excluded", "formality_target", "wardrobe_override"}


@pytest.fixture
def wardrobe():
    return [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]


def arguments(case):
    return {key: value for key, value in case["input"].items() if key in FILTER_KEYS}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_reference_filter_assertions(case, wardrobe):
    before = [item.model_dump() for item in wardrobe]
    result = filter_candidates(wardrobe, **arguments(case))
    candidates = result["candidates"]
    ids = {item.id for item in candidates}
    expected = case["expect"]
    scoped_ids = set(case["input"].get("wardrobe_override", [item.id for item in wardrobe]))
    assert ids <= scoped_ids
    assert ids.isdisjoint(expected.get("must_not_use", []))
    assert ids.isdisjoint(case["input"].get("excluded", []))
    assert len(ids) == len(candidates)

    count = count_composable_sets(candidates, result["band"])
    assert result["composable_count"] == count
    if "set_count" in expected:
        assert count >= expected["set_count"]
    if "set_count_lt" in expected:
        assert count < expected["set_count_lt"]
    if "set_count_lte" in expected:
        assert count <= expected["set_count_lte"]
    if expected.get("must_emit_shortage_hint"):
        shortage = result["shortage"]
        assert shortage["missing_slots"]
        assert shortage["requirements"]
        assert shortage["message"]
        for requirement in shortage["requirements"]:
            assert requirement["slot"] in shortage["missing_slots"]
            assert requirement["warmth_min"] >= SPEC["allowed_warmth"][result["band"]][0]
    else:
        assert result["shortage"] is None
    if expected.get("no_season_conflict"):
        assert all(set(item.seasons) & set(SPEC["allowed_seasons"][result["band"]]) for item in candidates)
    if expected.get("must_have_outer"):
        assert any(item.category == "outer" for item in candidates)
    if "must_have_categories" in expected:
        assert set(expected["must_have_categories"]) <= {item.category for item in candidates}
    if "distinct_sets_across_runs_gte" in expected:
        assert count >= expected["distinct_sets_across_runs_gte"]

    # 只证明指定编排约束仍有足够候选，不冒充已经生成/审核方案。
    feasible = candidates
    if "outer_in" in expected:
        feasible = [item for item in feasible if item.category != "outer" or item.id in expected["outer_in"]]
    if "must_use_any_of" in expected:
        required_ids = set(expected["must_use_any_of"])
        required_categories = {item.category for item in wardrobe if item.id in required_ids}
        feasible = [item for item in feasible if item.category not in required_categories or item.id in required_ids]
    if "set_count" in expected:
        assert count_composable_sets(feasible, result["band"]) >= expected["set_count"]
    assert [item.model_dump() for item in wardrobe] == before


@pytest.mark.parametrize("case_id,band", [("B07", "hot"), ("B08", "cool"), ("C02", "cold")])
def test_case_temperature_boundaries(case_id, band):
    assert temperature_band(CASES[case_id]["input"]["temp_c"]) == band


def test_warm_lower_boundary_comes_from_spec():
    lower = int(SPEC["band_by_temp"]["warm"].split("-")[0])
    assert temperature_band(lower) == "warm"


@pytest.mark.parametrize("value", ["冷", None, True])
def test_temperature_rejects_non_integer_input(value):
    with pytest.raises(TypeError, match="整数"):
        temperature_band(value)


def test_explicit_formality_target_overrides_occasion_default(wardrobe):
    inputs = arguments(CASES["C01"])
    inputs["occasion"] = CASES["B04"]["input"]["occasion"]
    result = filter_candidates(wardrobe, **inputs)
    lower, upper = inputs["formality_target"]
    assert result["candidates"]
    assert all(lower <= item.formality <= upper for item in result["candidates"])


def test_formality_defaults_to_spec_when_not_provided(wardrobe):
    inputs = arguments(CASES["B01"])
    inputs.pop("formality_target")
    result = filter_candidates(wardrobe, **inputs)
    lower, upper = SPEC["occasion_formality"][inputs["occasion"]]
    assert result["candidates"]
    assert all(lower <= item.formality <= upper for item in result["candidates"])


def test_empty_override_means_empty_wardrobe_with_shortage(wardrobe):
    inputs = arguments(CASES["C02"]) | {"wardrobe_override": []}
    result = filter_candidates(wardrobe, **inputs)
    assert result["candidates"] == []
    assert result["composable_count"] == 0
    assert result["shortage"]["missing_slots"]


def test_shoes_ignore_warmth_in_hot_band(wardrobe):
    """鞋无保暖等级语义：一双被模型标成 warmth=3 的板鞋，在 28℃ 仍必须可选。

    真实事故：拼色板鞋（单层皮革，夏天可穿）被判 warmth=3，26℃ 以上被温度带过滤掉，
    用户看到"我明明有这双鞋，系统说夏天没鞋穿"。豁免名单来自 filter_spec.warmth_exempt_slots。
    """
    board_shoe = wardrobe[0].model_copy(update={
        "id": "SHOE_BOARD", "category": "shoes", "sub": "板鞋",
        "warmth": 3, "formality": 1,
        "seasons": ["spring", "summer", "autumn", "winter"],
    })
    result = filter_candidates([board_shoe, *wardrobe], temp_c=28, occasion="weekend")
    assert "SHOE_BOARD" in {item.id for item in result["candidates"]}


def test_shoes_still_filtered_by_season(wardrobe):
    """豁免的只有 warmth，seasons 照旧生效：冬靴不该出现在 28℃ 的候选里。"""
    winter_boot = wardrobe[0].model_copy(update={
        "id": "SHOE_BOOT", "category": "shoes", "sub": "雪地靴",
        "warmth": 5, "formality": 1, "seasons": ["winter"],
    })
    result = filter_candidates([winter_boot, *wardrobe], temp_c=28, occasion="weekend")
    assert "SHOE_BOOT" not in {item.id for item in result["candidates"]}


def test_season_overlap_keeps_multiseason_item(wardrobe):
    expanded = wardrobe[0].model_copy(update={        "seasons": list(dict.fromkeys(season for seasons in SPEC["allowed_seasons"].values() for season in seasons)),
    })
    result = filter_candidates([expanded, *wardrobe[1:]], **arguments(CASES["B08"]))
    assert expanded.id in {item.id for item in result["candidates"]}


def test_dress_replaces_top_and_bottom(wardrobe):
    dress = wardrobe[0].model_copy(update={"category": "dress"})
    shoes = [item for item in wardrobe if item.category == "shoes"]
    result = filter_candidates([dress, *shoes], **arguments(CASES["B04"]))
    # dress 替代 top+bottom 后，每双合格鞋各成一套；件数随衣柜增长，不能写死。
    eligible_shoes = [item for item in result["candidates"] if item.category == "shoes"]
    assert len(eligible_shoes) > 1, "至少要有两双合格鞋，否则测不到鞋的替换语义"
    assert result["composable_count"] == len(eligible_shoes)
    assert result["shortage"] is None


def test_count_has_no_file_io_and_does_not_count_duplicate_ids(wardrobe, monkeypatch):
    result = filter_candidates(wardrobe, **arguments(CASES["B08"]))
    candidates = result["candidates"]
    expected = result["composable_count"]

    def forbidden_read(*args, **kwargs):
        raise AssertionError("组合计数不得读取文件。")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    assert count_composable_sets(candidates, result["band"]) == expected
    assert count_composable_sets([*candidates, candidates[0]], result["band"]) == expected
