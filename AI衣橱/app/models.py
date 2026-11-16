from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, ClassVar, Literal, Self, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Source = Literal["user", "model", "derived"]
Category = Literal["top", "bottom", "dress", "outer", "shoes", "accessory"]
Season = Literal["spring", "summer", "autumn", "winter"]
Occasion = Literal["commute", "date", "weekend", "client_meeting"]
SessionStatus = Literal["ok", "degraded", "failed"]
FallbackType = Literal["timeout", "parse_fail", "no_compliant_set"]
Score = Annotated[int, Field(ge=1, le=5, strict=True)]


def sourced(source: Source, **options):
    return Field(json_schema_extra={"source": source}, **options)


def derive_needs_confirm(*, uploaded: bool, user_edited: bool) -> bool:
    """D10-b：上传未经用户处理一律待确认，confidence不参与放行。"""
    return uploaded and not user_edited


class WardrobePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sub: str | None = None
    colors: list[str] = Field(default_factory=list)
    material: str | None = None
    pattern: str | None = None
    category: Category | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("请至少修改一个字段。")
        if "category" in self.model_fields_set and self.category is None:
            raise ValueError("品类必须选择有效值。")
        return self


class SourcedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: dict[str, Source] = sourced("derived", default_factory=dict)
    source_audit_types: ClassVar[dict[str, type[BaseModel]]] = {}

    @model_validator(mode="after")
    def complete_sources(self) -> Self:
        fields = type(self).model_fields
        if set(self.sources) - set(fields) - set(self.source_audit_types):
            raise ValueError("字段来源包含未知字段。")
        for name, value in self.sources.items():
            if name in self.source_audit_types:
                if not isinstance(value, self.source_audit_types[name]):
                    raise ValueError("来源审计元数据类型无效。")
            elif value not in get_args(Source):
                raise ValueError("普通字段来源只能是user/model/derived。")
        defaults = {
            name: field.json_schema_extra["source"]
            for name, field in fields.items()
        }
        self.sources = defaults | self.sources
        return self


class CorrectionAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["derived"] = "derived"
    entries: list[str]


class UploadAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["derived"] = "derived"
    draft_id: UUID
    photo_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class OwnedModel(SourcedModel):
    # legacy仅用于迁移/离线基准；HTTP入口必须提供真实设备UUID。
    owner_id: UUID | Literal["legacy"] = sourced("derived", default="legacy")


class DailyQuota(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    day: str
    recognition: int = Field(default=0, ge=0, le=20)
    composition: int = Field(default=0, ge=0, le=30)
    expires_at: str


class WardrobeItem(OwnedModel):
    source_audit_types: ClassVar[dict[str, type[BaseModel]]] = {
        "_corrections": CorrectionAudit, "_upload": UploadAudit,
    }
    sources: dict[str, Source | CorrectionAudit | UploadAudit] = sourced("derived", default_factory=dict)
    id: str = sourced("derived", min_length=1)
    name: str | None = sourced("model", default=None)
    image_path: str | None = sourced("user", default=None)
    category: Category | None = sourced("model", default=None)
    sub: str | None = sourced("model", default=None)
    colors: list[str] = sourced("model", default_factory=list)
    material: str | None = sourced("model", default=None)
    pattern: str | None = sourced("model", default=None)
    warmth: Score | None = sourced("model", default=None)
    formality: Score | None = sourced("model", default=None)
    seasons: list[Season] = sourced("model", default_factory=list)
    confidence: float | None = sourced("model", default=None, ge=0, le=1)
    needs_confirm: bool = sourced("derived", default=False)
    user_edited: bool = sourced("derived", default=False)
    created_at: datetime = sourced(
        "derived", default_factory=lambda: datetime.now(UTC)
    )

    def apply_user_patch(self, patch: WardrobePatch) -> Self:
        changes = patch.model_dump(exclude_unset=True)
        values = self.model_dump() | changes
        values["sources"] = self.sources | dict.fromkeys(changes, "user")
        return type(self).model_validate(values).confirm_recognition()

    def confirm_recognition(self) -> Self:
        values = self.model_dump()
        values["user_edited"] = True
        values["needs_confirm"] = derive_needs_confirm(
            uploaded=isinstance(self.sources.get("_upload"), UploadAudit), user_edited=True,
        )
        values["sources"] = self.sources | {
            "user_edited": "derived", "needs_confirm": "derived",
        }
        return type(self).model_validate(values)


class Session(OwnedModel):
    id: str = sourced("derived", min_length=1)
    temp_c: int = sourced("user", strict=True)
    occasion: Occasion = sourced("user")
    formality_target: tuple[Score, Score] = sourced("derived")
    excluded_items: list[str] = sourced("user", default_factory=list)
    status: SessionStatus = sourced("derived", default="ok")
    fallback_type: FallbackType | None = sourced("derived", default=None)
    latency_ms: int = sourced("derived", default=0, ge=0, strict=True)
    prompt_version: str = sourced("derived", min_length=1)

    @model_validator(mode="after")
    def validate_formality_range(self) -> Self:
        if self.formality_target[0] > self.formality_target[1]:
            raise ValueError("正式度区间下限不能大于上限。")
        return self


class OutfitSet(OwnedModel):
    id: str = sourced("derived", min_length=1)
    session_id: str = sourced("derived", min_length=1)
    rank: int = sourced("derived", ge=1, le=3, strict=True)
    reason: str = sourced("model", min_length=1)
    shortage_hint: str | None = sourced("derived", default=None)
    degraded: bool = sourced("derived", default=False)


class OutfitItem(OwnedModel):
    set_id: str = sourced("derived", min_length=1)
    # 校验不会把模型选出的值改成 derived；规则降级时可显式记录 derived。
    item_id: str = sourced("model", min_length=1)
    slot: Category = sourced("model")


class SeedData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    wardrobe: list[WardrobeItem]


# 槽位值从既有品类定义派生；校验器只引用这里的常量。
Slot = Enum("Slot", {value.upper(): value for value in get_args(Category)}, type=str)
STANDARD_SLOTS = frozenset((Slot.TOP, Slot.BOTTOM, Slot.SHOES))
DRESS_SLOTS = frozenset((Slot.DRESS, Slot.SHOES))
OUTER_BANDS = frozenset(("cool", "cold"))
ItemID = Annotated[str, Field(min_length=1, strict=True)]


class OutfitSlots(BaseModel):
    """全部字段均由模型选择；未使用的槽位必须显式为 null。"""

    model_config = ConfigDict(extra="forbid")
    top: ItemID | None
    bottom: ItemID | None
    outer: ItemID | None
    shoes: ItemID | None
    dress: ItemID | None


class ProposedOutfit(BaseModel):
    """slots、reason 均为模型产出，不与持久化的 derived 字段混合。"""

    model_config = ConfigDict(extra="forbid")
    slots: OutfitSlots
    reason: str = Field(min_length=1, strict=True)


class Composition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sets: list[ProposedOutfit] = Field(min_length=1, max_length=3)


class ShortageRequirement(BaseModel):
    slot: Slot
    warmth_min: Score
    formality_min: Score


class Shortage(BaseModel):
    missing_slots: list[Slot]
    requirements: list[ShortageRequirement]
    message: str


class ErrorCategory(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PARSE = "parse"
    NETWORK = "network"


class DegradeReason(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PARSE_FAILED = "parse_failed"


class ComposeResult(BaseModel):
    """sets 为模型产出；其余字段由代码计算，shortage 来自 S2。"""

    sets: list[ProposedOutfit] = Field(default_factory=list)
    shortage: Shortage | None = None
    shortage_hint: str | None = None
    degraded: bool = False
    latency_ms: int = Field(default=0, ge=0)
    prompt_version: str = "outfit_compose.v1"
    degrade_reason: DegradeReason | None = None


class ComposeFailure(BaseModel):
    attribution: Literal["PARSE", "COMPOSE"]
    code: Literal["INVALID_OUTPUT", "MODEL_TIMEOUT", "MODEL_CONFIG", "MODEL_NETWORK", "MODEL_RESPONSE"]
    message: str
    errors: list[str] = Field(default_factory=list)


class ProviderMessage(BaseModel):
    content: str


class ProviderChoice(BaseModel):
    message: ProviderMessage
    finish_reason: str | None = None


class ProviderUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ProviderCompletion(BaseModel):
    choices: list[ProviderChoice] = Field(min_length=1)
    usage: ProviderUsage = Field(default_factory=ProviderUsage)


class ProviderError(BaseModel):
    code: str | None = None


class ProviderErrorEnvelope(BaseModel):
    error: ProviderError


class OutfitsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temp_c: int = Field(strict=True)
    occasion: Occasion
    formality_target: tuple[Score, Score] | None = None
    excluded: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered_formality(self) -> Self:
        if self.formality_target is not None and self.formality_target[0] > self.formality_target[1]:
            raise ValueError("正式度区间下限不能大于上限。")
        return self


class OutfitView(BaseModel):
    id: str
    rank: int = Field(ge=1, le=3)
    slots: OutfitSlots
    reason: str
    items: list[WardrobeItem]


class OutfitsResponse(BaseModel):
    session_id: str
    sets: list[OutfitView]
    shortage: dict[Slot, ShortageRequirement] | None = None
    shortage_hint: str | None = None
    degraded: bool
    degrade_reason: DegradeReason | None
    prompt_version: str
    latency_ms: int = Field(ge=0)


class WardrobeUploadResponse(BaseModel):
    """items属性来源见各自sources，其余响应元数据由代码计算。"""
    draft_id: UUID
    items: list[WardrobeItem]
    corrections: list[str]
    latency_ms: int = Field(ge=0)
    prompt_version: str = "item_extract.v2"
    reused: bool = False


class ExtractionFailureResponse(BaseModel):
    detail: str
    category: ErrorCategory | None
    code: Literal["IN_PARSE", "MODEL_CONFIG", "MODEL_NETWORK", "MODEL_TIMEOUT", "MODEL_RESPONSE", "NOT_CLOTHING"]
