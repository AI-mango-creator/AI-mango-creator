import { DeviceIdError, deviceHeaders, getDeviceId } from "./deviceId";

export const categoryLabels = {
  top: "上装", bottom: "下装", dress: "连衣裙", outer: "外套", shoes: "鞋", accessory: "配饰",
} as const;

export type Category = keyof typeof categoryLabels;
type Source = "user" | "model" | "derived";
type SourceAudit = { source: "derived"; entries: string[] } |
  { source: "derived"; draft_id: string; photo_sha256: string };

export type WardrobeItem = {
  id: string;
  owner_id: string;
  name: string | null;
  image_path: string | null;
  category: Category | null;
  sub: string | null;
  colors: string[];
  material: string | null;
  pattern: string | null;
  warmth: number | null;
  formality: number | null;
  seasons: ("spring" | "summer" | "autumn" | "winter")[];
  confidence: number | null;
  needs_confirm: boolean;
  user_edited: boolean;
  created_at: string;
  sources: Record<string, Source | SourceAudit>;
};

export type WardrobePatch = Partial<Pick<WardrobeItem, "sub" | "colors" | "material" | "pattern">> & {
  category?: Category;
};
type Fetcher = typeof fetch;
class ApiError extends Error {}

async function request(path: string, options: RequestInit, fetcher: Fetcher, uploading = false, format: "json" | "blob" = "json"): Promise<unknown> {
  // 识别最多3次调用+一次限流等待；上传不能沿用GET的10s超时。
  const timeout = AbortSignal.timeout(uploading ? 75000 : 10000);
  try {
    const response = await fetcher(path, {
      ...options, headers: deviceHeaders(options.headers),
      signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
    });
    const payload: unknown = response.status === 204 ? null :
      response.ok && format === "blob" ? await response.blob() : await response.json();
    if (!response.ok) {
      const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
      throw new ApiError(typeof detail === "string" ? detail : "请求失败，请重新加载后重试。");
    }
    return payload;
  } catch (error) {
    if (error instanceof ApiError || error instanceof DeviceIdError || options.signal?.aborted) throw error;
    if (timeout.aborted) throw new ApiError(uploading ? "上传等待超时，图片已保留。请重试，或稍后再试。" : "请求超时，请重新加载后重试。");
    throw new ApiError(uploading ? "连接失败，图片已保留。请重试，或稍后再试。" : "连接失败，请检查服务是否启动，然后重新加载。");
  }
}

function ownsItems(items: unknown[]): boolean {
  const owner = getDeviceId();
  return items.every((item) => !!item && typeof item === "object" && "owner_id" in item && item.owner_id === owner);
}

export async function getWardrobePhoto(id: string, signal?: AbortSignal, fetcher: Fetcher = fetch): Promise<Blob> {
  const photo = await request(`/api/wardrobe/items/${encodeURIComponent(id)}/photo`, { signal }, fetcher, false, "blob");
  if (!(photo instanceof Blob) || !photo.type.startsWith("image/")) throw new ApiError("照片响应无效，请稍后重试。");
  return photo;
}

export type ItemPhotoState = { status: "loading" | "ready" | "error"; url: string };

export function watchWardrobePhoto(id: string, onState: (state: ItemPhotoState) => void, fetcher: Fetcher = fetch) {
  const controller = new AbortController();
  let objectUrl = "";
  function release() {
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = ""; }
  }
  function fail() {
    release();
    if (!controller.signal.aborted) onState({ status: "error", url: "" });
  }
  onState({ status: "loading", url: "" });
  void getWardrobePhoto(id, controller.signal, fetcher).then((blob) => {
    if (controller.signal.aborted) return;
    objectUrl = URL.createObjectURL(blob);
    onState({ status: "ready", url: objectUrl });
  }).catch(fail);
  return { fail, dispose() { controller.abort(); release(); } };
}

export async function deleteWardrobeItem(items: WardrobeItem[], id: string, fetcher: Fetcher = fetch): Promise<WardrobeItem[]> {
  await request(`/api/wardrobe/items/${encodeURIComponent(id)}`, { method: "DELETE" }, fetcher);
  return items.filter((item) => item.id !== id);
}

export async function clearWardrobe(fetcher: Fetcher = fetch): Promise<Record<string, number>> {
  return await request("/api/wardrobe/items", { method: "DELETE" }, fetcher) as Record<string, number>;
}

export async function getWardrobe(signal?: AbortSignal, fetcher: Fetcher = fetch): Promise<WardrobeItem[]> {
  const payload = await request("/api/wardrobe/items", { signal }, fetcher);
  if (!Array.isArray(payload)) throw new ApiError("衣柜响应格式有误，请重新加载。");
  if (!ownsItems(payload)) throw new ApiError("衣柜响应归属不一致，请重新加载。原数据不会被覆盖。");
  return payload as WardrobeItem[];
}

export async function loadWardrobe(
  signal: AbortSignal, onLoaded: (items: WardrobeItem[]) => void, onError: (message: string) => void,
  fetcher: Fetcher = fetch, isErrorCurrent: () => boolean = () => true,
): Promise<void> {
  try {
    const loaded = await getWardrobe(signal, fetcher);
    if (!signal.aborted) onLoaded(loaded);
  } catch (error) {
    if (!signal.aborted && isErrorCurrent()) onError(error instanceof Error ? error.message : "衣柜加载失败，请重新加载。");
  }
}

export async function saveWardrobeItem(
  items: WardrobeItem[], id: string, patch: WardrobePatch, fetcher: Fetcher = fetch,
): Promise<WardrobeItem[]> {
  if (Object.keys(patch).length === 0) {
    if (items.find((item) => item.id === id)?.needs_confirm) return confirmWardrobeItem(items, id, fetcher);
    throw new ApiError("请先修改至少一项内容。");
  }
  const payload = await request(`/api/wardrobe/items/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify(patch),
  }, fetcher);
  if (!payload || typeof payload !== "object" || !("id" in payload) || payload.id !== id) {
    throw new ApiError("保存响应与当前单品不一致，请重新加载。");
  }
  if (!ownsItems([payload])) throw new ApiError("保存响应归属不一致，请重新加载。");
  const updated = payload as WardrobeItem;
  return items.map((item) => item.id === id ? updated : item);
}

export async function confirmWardrobeItem(
  items: WardrobeItem[], id: string, fetcher: Fetcher = fetch,
): Promise<WardrobeItem[]> {
  const payload = await request(`/api/wardrobe/items/${encodeURIComponent(id)}/confirm`, { method: "POST" }, fetcher);
  if (!payload || typeof payload !== "object" || !("id" in payload) || payload.id !== id || !ownsItems([payload]) ||
      !("needs_confirm" in payload) || payload.needs_confirm !== false) {
    throw new ApiError("确认响应无效，请稍后重试。");
  }
  return items.map((item) => item.id === id ? payload as WardrobeItem : item);
}

export type PhotoDraft = { id: string; file: File; stage: "uploading" | "error" | "done"; error: string };
export type PhotoUploadResponse = {
  draft_id: string; items: WardrobeItem[]; corrections: string[]; latency_ms: number;
  prompt_version: string; reused: boolean;
};

export function createPhotoDraft(file: File, id: string = crypto.randomUUID()): PhotoDraft {
  return { id, file, stage: "uploading", error: "" };
}

export function hasUploadPlaceholder(draft: PhotoDraft | null): boolean {
  return draft !== null && draft.stage !== "done";
}

export function mergeWardrobeItems(items: WardrobeItem[], added: WardrobeItem[]): WardrobeItem[] {
  const addedIds = new Set(added.map((item) => item.id));
  return [...added, ...items.filter((item) => !addedIds.has(item.id))];
}

export async function submitPhotoDraft(
  draft: PhotoDraft, onDraft: (next: PhotoDraft) => void, fetcher: Fetcher = fetch,
  onSuccess?: () => void,
): Promise<PhotoUploadResponse | null> {
  onDraft({ ...draft, stage: "uploading", error: "" });
  const body = new FormData();
  body.append("photo", draft.file);
  body.append("draft_id", draft.id);
  try {
    const payload = await request("/api/wardrobe/items", { method: "POST", body }, fetcher, true);
    if (!payload || typeof payload !== "object" || !("draft_id" in payload) || payload.draft_id !== draft.id ||
        !("items" in payload) || !Array.isArray(payload.items) || payload.items.length === 0 ||
        payload.items.some((item) => !item || typeof item.id !== "string")) {
      throw new ApiError("建档响应无效，图片已保留，请原地重试。");
    }
    if (!ownsItems(payload.items)) throw new ApiError("建档响应归属不一致，图片已保留，请原地重试。");
    onSuccess?.();
    onDraft({ ...draft, stage: "done", error: "" });
    return payload as PhotoUploadResponse;
  } catch (error) {
    onDraft({ ...draft, stage: "error", error: error instanceof Error ? error.message : "上传失败，图片已保留，可原地重试。" });
    return null;
  }
}
