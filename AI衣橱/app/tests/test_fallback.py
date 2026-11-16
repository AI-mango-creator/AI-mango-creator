import json
from pathlib import Path

import pytest

from app.llm.errors import FallbackValidationError
from app.models import Composition, WardrobeItem
from app.services import fallback
from app.services.compose import generate_outfits
from app.services.filter import filter_candidates
from app.services.validate import validate_outfits

DATA = json.loads((Path(__file__).resolve().parents[2] / "cases/cases.json").read_text())


@pytest.fixture
def filtered():
    return filter_candidates(
        [WardrobeItem.model_validate(item) for item in DATA["wardrobe"]],
        temp_c=18, occasion="commute",
    )


def test_three_rule_strategies_pass_real_validator(filtered):
    result = fallback.fallback_outfits(filtered["candidates"], band="cool", degrade_reason="timeout")
    assert result.degraded is True
    assert result.degrade_reason == "timeout"
    assert len(result.sets) == 3
    assert validate_outfits(Composition(sets=result.sets), filtered["candidates"], band="cool", expected_count=3) == []
    assert "正式度从高到低" in result.sets[0].reason
    assert "正式度从低到高" in result.sets[1].reason
    assert "厚薄从高到低" in result.sets[2].reason


@pytest.mark.parametrize("mutation", ["outside", "two_tops", "duplicate"])
def test_template_injection_cannot_bypass_validator(filtered, monkeypatch, mutation):
    clean = fallback._template_composition(filtered["candidates"], "cool")
    payload = clean.model_dump()
    slots = payload["sets"][0]["slots"]
    if mutation == "outside":
        slots["top"] = "W99"
    elif mutation == "duplicate":
        slots["bottom"] = slots["top"]
    else:
        slots["bottom"] = next(item.id for item in filtered["candidates"]
                               if item.category == "top" and item.id != slots["top"])
    poisoned = Composition.model_validate(payload)
    monkeypatch.setattr(fallback, "_template_composition", lambda candidates, band: poisoned)
    with pytest.raises(FallbackValidationError) as error:
        fallback.fallback_outfits(filtered["candidates"], band="cool", degrade_reason="timeout")
    assert error.value.errors
    if mutation == "outside":
        assert any("候选集" in message for message in error.value.errors)


def test_partial_fallback_does_not_duplicate_sets(filtered):
    example = fallback._template_composition(filtered["candidates"], "cool").sets[0]
    ids = set(example.slots.model_dump(exclude_none=True).values())
    candidates = [item for item in filtered["candidates"] if item.id in ids]
    result = fallback.fallback_outfits(candidates, band="cool", degrade_reason="rate_limit")
    assert len(result.sets) == 1
    assert result.shortage_hint
    assert validate_outfits(Composition(sets=result.sets), candidates, band="cool", expected_count=1) == []


@pytest.mark.parametrize("case_id", ["C01", "C02"])
def test_shortage_does_not_enter_model_or_fallback(case_id, monkeypatch):
    case = next(case for case in DATA["cases"] if case["id"] == case_id)
    inputs = case["input"]
    keys = {"temp_c", "occasion", "formality_target", "excluded", "wardrobe_override"}
    filtered = filter_candidates([WardrobeItem.model_validate(item) for item in DATA["wardrobe"]],
                                 **{key: value for key, value in inputs.items() if key in keys})

    def forbidden(*args, **kwargs):
        pytest.fail("shortage 不应调用模型或规则降级")

    monkeypatch.setattr(fallback, "fallback_outfits", forbidden)
    result = generate_outfits(filtered, temp_c=inputs["temp_c"], occasion=inputs["occasion"], chat=forbidden)
    assert result.sets == []
    assert result.shortage
    assert result.degraded is False


def test_no_compliant_rule_set_is_not_forced():
    with pytest.raises(FallbackValidationError):
        fallback.fallback_outfits([], band="cool", degrade_reason="timeout")


@pytest.mark.parametrize("case", [case for case in DATA["cases"] if case["id"].startswith("B")],
                         ids=lambda case: case["id"])
def test_fallback_respects_all_scene_bands(case):
    keys = {"temp_c", "occasion", "formality_target", "excluded", "wardrobe_override"}
    filtered = filter_candidates([WardrobeItem.model_validate(item) for item in DATA["wardrobe"]],
                                 **{key: value for key, value in case["input"].items() if key in keys})
    result = fallback.fallback_outfits(filtered["candidates"], band=filtered["band"], degrade_reason="timeout")
    assert len(result.sets) == case["expect"]["set_count"]
    assert validate_outfits(Composition(sets=result.sets), filtered["candidates"],
                            band=filtered["band"], expected_count=len(result.sets)) == []
