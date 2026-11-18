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
WardrobeGroup = Literal['tops', 'bottoms', 'skirts', 'sets', 'shoes', 'bags', 'jewelry', 'accessories', 'unclassified']
STORAGE_ONLY_GROUPS = frozenset(('sets', 'bags', 'jewelry', 'unclassified'))


def wardrobe_group_for(category, sub):
    if category == 'bottom' and '裙' in (sub or ''):
        return 'skirts'
    return {'top': 'tops', 'outer': 'tops', 'bottom': 'bottoms', 'dress': 'skirts',
            'shoes': 'shoes', 'accessory': 'accessories'}.get(category, 'unclassified')


def category_for_group(group, sub):
    if group in STORAGE_ONLY_GROUPS:
        return None
    if group == 'tops':
        if any(word in (sub or '') for word in ('外套', '夹克', '大衣', '风衣', '羽绒', '冲锋', '防晒服')):
            return 'outer'
        return 'top' if any(word in (sub or '') for word in ('衬衫', 'T恤', '毛衣', '卫衣', '背心', '针织', '上衣')) else None
    if group == 'skirts':
        if '连衣' in (sub or ''):
            return 'dress'
        if '裙' in (sub or ''):
            return 'bottom'
        return None
    return {'bottoms': 'bottom', 'shoes': 'shoes', 'accessories': 'accessory'}[group]


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
    wardrobe_group: WardrobeGroup | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("请至少修改一个字段。")
        if "category" in self.model_fields_set and self.category is None:
            raise ValueError("品类必须选择有效值。")
        if ('wardrobe_group' in self.model_fields_set
                and (self.wardrobe_group in (None, 'unclassified') or not (self.sub and self.sub.strip()))):
            raise ValueError('请选择明确分类并填写具体品类名称。')
        if 'wardrobe_group' in self.model_fields_set and 'category' in self.model_fields_set:
            compatible = {'tops': {'top', 'outer'}, 'skirts': {'bottom', 'dress'},
                          'bottoms': {'bottom'}, 'shoes': {'shoes'}, 'accessories': {'accessory'}}
            if self.category not in compatible.get(self.wardrobe_group, set()):
                raise ValueError('搭配位置与衣橱分类不一致。')
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
    prompt_version: Literal['item_extract.v2', 'item_extract.v3'] = 'item_extract.v2'


class OwnedModel(SourcedModel):
    # legacy仅用于迁移/离线基准；HTTP入口必须提供真实设备UUID。
    owner_id: UUID | Literal["legacy"] = sourced("derived", default="legacy")


BodyShape = Literal["X", "A", "TY", "H", "O"]


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    height_cm: float | None = Field(default=None, gt=0)
    weight_kg: float | None = Field(default=None, gt=0)
    body_shape: BodyShape | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("请至少填写或清除一项身材资料。")
        return self


class BodyProfile(OwnedModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    height_cm: float | None = sourced("user", default=None, gt=0)
    weight_kg: float | None = sourced("user", default=None, gt=0)
    body_shape: BodyShape | None = sourced("user", default=None)


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
    wardrobe_group: WardrobeGroup | None = sourced('derived', default=None)
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

    @model_validator(mode='after')
    def derive_group(self) -> Self:
        if self.wardrobe_group is None:
            self.wardrobe_group = wardrobe_group_for(self.category, self.sub)
            self.sources['wardrobe_group'] = 'derived'
        if self.wardrobe_group in STORAGE_ONLY_GROUPS and self.category is not None:
            self.category = None
            self.sources['category'] = 'derived'
        return self

    def apply_user_patch(self, patch: WardrobePatch) -> Self:
        changes = patch.model_dump(exclude_unset=True)
        values = self.model_dump() | changes
        values["sources"] = self.sources | dict.fromkeys(changes, "user")
        if 'wardrobe_group' in changes:
            mapped = changes['category'] if 'category' in changes else category_for_group(changes['wardrobe_group'], values['sub'])
            if mapped != values['category']:
                values['category'] = mapped
                values['sources']['category'] = 'derived'
        elif 'category' in changes or ('sub' in changes and self.sources['wardrobe_group'] != 'user'):
            values['wardrobe_group'] = wardrobe_group_for(values['category'], values['sub'])
            values['sources']['wardrobe_group'] = 'derived'
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


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    category: Literal['top', 'bottom', 'dress', 'outer', 'shoes', 'accessory', 'set', 'bag', 'jewelry', 'unknown']
    sub: str | None
    colors: list[str]
    material: str | None
    pattern: str | None
    warmth: Score | None
    formality: Score | None
    seasons: list[Season]
    confidence: float = Field(ge=0, le=1)


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[ExtractedItem]


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


# 天气来自外部预报服务，独立协议，不改变衣物来源或现有业务模型。
class WeatherCity(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    admin1: str = ''
    country: str = ''
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str


class WeatherCities(BaseModel):
    cities: list[WeatherCity] = Field(max_length=5)


class WeatherDay(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    date: str
    temp_min_c: float = Field(ge=-100, le=70)
    temp_max_c: float = Field(ge=-100, le=70)
    weather_code: int
    weather_text: str
    advice: str

    @model_validator(mode='after')
    def valid_range(self) -> Self:
        if self.temp_min_c > self.temp_max_c:
            raise ValueError('最低温高于最高温')
        return self


class WeatherForecast(BaseModel):
    provider: Literal['Open-Meteo'] = 'Open-Meteo'
    timezone: str
    fetched_at: datetime
    days: list[WeatherDay] = Field(min_length=7, max_length=7)


CommunityKind = Literal['photo', 'outfit', 'poll', 'buy']
CommunityTab = Literal['following', 'all', 'outfits', 'votes']


class CommunityTimed(SourcedModel):
    created_at: str = sourced('derived', default_factory=lambda: datetime.now(UTC).isoformat())


class CommunityAuthor(CommunityTimed):
    id: str = sourced('derived')
    owner_id: UUID = sourced('derived')
    nickname: str = sourced('derived')


class CommunityPost(CommunityTimed):
    id: str = sourced('derived')
    author_id: str = sourced('derived')
    kind: CommunityKind = sourced('user')
    title: str = sourced('user', min_length=1, max_length=80)
    body: str = sourced('user', default='', max_length=2000)
    draft_id: str = sourced('user')
    request_hash: str = sourced('derived', min_length=64, max_length=64)


class CommunityMedia(SourcedModel):
    id: str = sourced('derived')
    post_id: str = sourced('derived')
    position: int = sourced('derived', ge=0)
    file_path: str = sourced('derived')
    mime_type: Literal['image/jpeg', 'image/png', 'image/webp'] = sourced('derived')
    caption: str = sourced('derived', default='')


class CommunityLike(CommunityTimed):
    post_id: str = sourced('derived')
    author_id: str = sourced('derived')


class CommunityFollow(CommunityTimed):
    follower_id: str = sourced('derived')
    followee_id: str = sourced('user')


class CommunityComment(CommunityTimed):
    id: str = sourced('derived')
    post_id: str = sourced('derived')
    author_id: str = sourced('derived')
    text: str = sourced('user', min_length=1, max_length=500)
    client_id: str = sourced('user')


class CommunityOption(SourcedModel):
    id: str = sourced('derived')
    post_id: str = sourced('derived')
    position: int = sourced('derived', ge=0)
    label: str = sourced('user', min_length=1, max_length=80)
    media_id: str | None = sourced('derived', default=None)


class CommunityVote(CommunityTimed):
    post_id: str = sourced('derived')
    author_id: str = sourced('derived')
    option_id: str = sourced('user')


class CommunityOptionDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=80)


class CommunityDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    draft_id: UUID
    kind: CommunityKind
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(default='', max_length=2000)
    item_ids: list[str] = Field(default_factory=list, max_length=8)
    options: list[CommunityOptionDraft] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def valid_kind(self) -> Self:
        if self.kind == 'outfit':
            if not 2 <= len(self.item_ids) <= 8 or len(set(self.item_ids)) != len(self.item_ids):
                raise ValueError('搭配分享请选择2至8件不同衣物')
        elif self.item_ids:
            raise ValueError('此类帖子不接受衣柜单品')
        if (self.kind == 'poll' and not 2 <= len(self.options) <= 4) or (self.kind != 'poll' and self.options):
            raise ValueError('穿搭投票需2至4个选项，其他类型不接受自定义选项')
        return self


class CommunityCommentDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    client_id: UUID
    text: str = Field(min_length=1, max_length=500)


class CommunityVoteDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    option_id: str = Field(min_length=1, max_length=80)


class CommunityAuthorView(BaseModel):
    id: str
    nickname: str


class CommunityMediaView(BaseModel):
    id: str
    caption: str


class CommunityOptionView(BaseModel):
    id: str
    label: str
    media_id: str | None
    votes: int


class CommunityPostView(BaseModel):
    id: str
    author: CommunityAuthorView
    kind: CommunityKind
    title: str
    body: str
    created_at: str
    media: list[CommunityMediaView]
    options: list[CommunityOptionView]
    likes: int
    comments: int
    votes: int
    liked: bool
    following: bool
    my_vote: str | None
    can_delete: bool


class CommunityFeed(BaseModel):
    posts: list[CommunityPostView]
    next_cursor: str | None


class CommunityCommentView(BaseModel):
    id: str
    author: CommunityAuthorView
    text: str
    created_at: str
    can_delete: bool


class CommunityComments(BaseModel):
    comments: list[CommunityCommentView]
    next_cursor: str | None
