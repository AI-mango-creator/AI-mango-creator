import copy
import json
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import Composition, WardrobeItem
from app.services.filter import filter_candidates
from app.services.validate import validate_outfits

DATA = json.loads((Path(__file__).resolve().parents[2] / "cases/cases.json").read_text())


@pytest.fixture
def filtered():
    wardrobe = [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]
    return filter_candidates(wardrobe, temp_c=18, occasion="commute")


@pytest.fixture
def valid_payload(filtered):
    groups = {
        slot: [item for item in filtered["candidates"] if item.category == slot]
        for slot in ("top", "bottom", "outer", "shoes")
    }
    sets = []
    for selection in product(*groups.values()):
        slots = dict(zip(groups, (item.id for item in selection))) | {"dress": None}
        sets.append({"slots": slots, "reason": f"采用{selection[0].colors[0]}上装。"})
        if len(sets) == 3:
            break
    return {"sets": sets}


def errors(payload, filtered):
    return validate_outfits(
        Composition.model_validate(payload), filtered["candidates"],
        band=filtered["band"], expected_count=3,
    )


def test_valid_three_sets(valid_payload, filtered):
    assert errors(valid_payload, filtered) == []


def test_two_tops_rejected(valid_payload, filtered):
    tops = [item.id for item in filtered["candidates"] if item.category == "top"]
    valid_payload["sets"][0]["slots"]["bottom"] = tops[1]
    assert any("槽位" in error for error in errors(valid_payload, filtered))


def test_outside_candidate_rejected(valid_payload, filtered):
    valid_payload["sets"][0]["slots"]["top"] = "W99"
    assert any("候选集" in error for error in errors(valid_payload, filtered))


@pytest.mark.parametrize("word", ["显瘦", "气质", "高级感", "百搭神器"])
def test_unverifiable_reason_rejected(word, valid_payload, filtered):
    valid_payload["sets"][0]["reason"] += word
    assert any("不可核对" in error for error in errors(valid_payload, filtered))


def test_duplicate_item_rejected(valid_payload, filtered):
    slots = valid_payload["sets"][0]["slots"]
    slots["bottom"] = slots["top"]
    assert any("重复单品" in error for error in errors(valid_payload, filtered))


def test_missing_outer_rejected(valid_payload, filtered):
    valid_payload["sets"][0]["slots"]["outer"] = None
    assert any("槽位" in error for error in errors(valid_payload, filtered))


def test_repeated_set_cannot_fill_three(valid_payload, filtered):
    valid_payload["sets"] = [copy.deepcopy(valid_payload["sets"][0]) for _ in range(3)]
    assert any("重复方案" in error for error in errors(valid_payload, filtered))


def test_reason_requires_actual_attribute(valid_payload, filtered):
    valid_payload["sets"][0]["reason"] = "今天这样穿很好。"
    assert any("真实属性" in error for error in errors(valid_payload, filtered))


@pytest.mark.parametrize("band", ["hot", "warm"])
def test_warm_bands_forbid_outer(band, valid_payload, filtered):
    assert any("槽位" in error for error in validate_outfits(
        Composition.model_validate(valid_payload), filtered["candidates"],
        band=band, expected_count=3,
    ))


def test_cold_inner_warmth_checked(valid_payload, filtered):
    wardrobe = [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]]
    thin_top = next(item for item in wardrobe if item.category == "top" and item.warmth < 3)
    valid_payload["sets"][0]["slots"]["top"] = thin_top.id
    assert any("保暖" in error for error in validate_outfits(
        Composition.model_validate(valid_payload), wardrobe, band="cold", expected_count=3,
    ))


def test_dress_replaces_top_bottom(valid_payload, filtered):
    dress = WardrobeItem(id="D1", category="dress", colors=["蓝色"], warmth=3, formality=3)
    outfit = valid_payload["sets"][0]
    outfit["slots"].update(top=None, bottom=None, dress=dress.id)
    outfit["reason"] = "采用蓝色连衣裙。"
    result = validate_outfits(
        Composition.model_validate({"sets": [outfit]}), [*filtered["candidates"], dress],
        band="cool", expected_count=1,
    )
    assert result == []
    outfit["slots"]["top"] = next(item.id for item in filtered["candidates"] if item.category == "top")
    assert any("槽位" in error for error in validate_outfits(
        Composition.model_validate({"sets": [outfit]}), [*filtered["candidates"], dress],
        band="cool", expected_count=1,
    ))


def test_multiple_items_in_slot_rejected_by_schema(valid_payload):
    valid_payload["sets"][0]["slots"]["top"] = ["W01", "W07"]
    with pytest.raises(ValidationError):
        Composition.model_validate(valid_payload)
