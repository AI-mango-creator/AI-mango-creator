import json
from contextlib import closing
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.db import connect_db, owner_lock, reserve_quota, to_db_values
from app.llm.errors import LLMError, ServiceError
from app.models import (
    OutfitItem,
    OutfitSet,
    OutfitsRequest,
    OutfitsResponse,
    OutfitView,
    Session,
)
from app.routers.wardrobe import Owner, database_path, list_items
from app.services.compose import PROMPT_VERSION, ComposeError, generate_outfits
from app.services.filter import filter_candidates

router = APIRouter(prefix="/api/outfits", tags=["搭配"])
DEFAULT_TARGETS = json.loads(
    (Path(__file__).resolve().parents[2] / "cases/cases.json").read_text(encoding="utf-8")
)["meta"]["filter_spec"]["occasion_formality"]


def _persist(path, session, sets):
    with closing(connect_db(path)) as connection, connection:
        for table, records in (
            ("sessions", [session]),
            ("outfit_sets", [record for record, items in sets]),
            ("outfit_items", [item for record, items in sets for item in items]),
        ):
            for record in records:
                if str(record.owner_id) != str(session.owner_id):
                    raise ValueError("方案归属与请求设备不一致。")
                values = to_db_values(record)
                names = ", ".join(values)
                parameters = ", ".join(f":{name}" for name in values)
                connection.execute(f"INSERT INTO {table} ({names}) VALUES ({parameters})", values)


def _record_latency(path, session_id, owner_id, started):
    # 统计读取、过滤、全部模型尝试和结果提交；最后一次计时字段回写不纳入自身。
    latency_ms = round((perf_counter() - started) * 1000)
    with closing(connect_db(path)) as connection, connection:
        connection.execute("UPDATE sessions SET latency_ms=? WHERE id=? AND owner_id=?", (latency_ms, session_id, owner_id))
    return latency_ms


@router.post("", response_model=OutfitsResponse)
def create_outfits(body: OutfitsRequest, path: Annotated[Path, Depends(database_path)], owner_id: Owner):
    started = perf_counter()
    with owner_lock(path, owner_id):
        return _create_outfits(body, path, owner_id, started)


def _create_outfits(body, path, owner_id, started):
    session_id = "S" + uuid4().hex
    target = body.formality_target if body.formality_target is not None else DEFAULT_TARGETS[body.occasion]
    session = Session(
        id=session_id, owner_id=owner_id, temp_c=body.temp_c, occasion=body.occasion,
        formality_target=target, excluded_items=body.excluded, prompt_version=PROMPT_VERSION,
        sources={"formality_target": "user" if body.formality_target is not None else "derived"},
    )
    wardrobe = list_items(path, owner_id)
    filtered = filter_candidates(wardrobe, temp_c=body.temp_c, occasion=body.occasion,
                                 formality_target=target, excluded=body.excluded)
    if filtered["composable_count"] > 0:
        reserve_quota(path, owner_id, "composition")
    try:
        result = generate_outfits(filtered, temp_c=body.temp_c, occasion=body.occasion,
                                  formality_target=target, case_id=session_id)
    except (ComposeError, LLMError, ServiceError):
        session.status = "failed"
        _persist(path, session, [])
        _record_latency(path, session_id, owner_id, started)
        raise
    session.status = "degraded" if result.degraded else "ok"
    # 老表仅支持这三种归因；auth/rate_limit 不冒充 timeout，精确值由响应携带。
    session.fallback_type = {"timeout": "timeout", "parse_failed": "parse_fail"}.get(result.degrade_reason)
    if result.shortage is not None:
        session.fallback_type = "no_compliant_set"
    by_id = {item.id: item for item in filtered["candidates"]}
    records, views = [], []
    origin = "derived" if result.degraded else "model"
    for rank, outfit in enumerate(result.sets, 1):
        set_id = f"{session_id}-{rank}"
        record = OutfitSet(id=set_id, owner_id=owner_id, session_id=session_id, rank=rank, reason=outfit.reason,
                           shortage_hint=result.shortage_hint, degraded=result.degraded,
                           sources={"reason": origin})
        slots = outfit.slots.model_dump(exclude_none=True)
        items = [OutfitItem(set_id=set_id, owner_id=owner_id, item_id=item_id, slot=slot,
                            sources={"item_id": origin, "slot": origin}) for slot, item_id in slots.items()]
        records.append((record, items))
        views.append(OutfitView(id=set_id, rank=rank, slots=outfit.slots, reason=outfit.reason,
                                items=[by_id[item_id] for item_id in slots.values()]))
    _persist(path, session, records)
    total_latency = _record_latency(path, session_id, owner_id, started)
    shortage = ({item.slot: item for item in result.shortage.requirements} if result.shortage else None)
    return OutfitsResponse(
        session_id=session_id, sets=views, shortage=shortage, shortage_hint=result.shortage_hint,
        degraded=result.degraded, degrade_reason=result.degrade_reason,
        prompt_version=result.prompt_version, latency_ms=total_latency,
    )
