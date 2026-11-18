import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPhotoDraft, getWardrobe, hasUploadPlaceholder, loadWardrobe, mergeWardrobeItems, saveWardrobeItem,
  submitPhotoDraft, type PhotoDraft, type WardrobeItem } from "./api";
import { getViewState } from "./viewState";

beforeEach(() => { vi.stubGlobal("localStorage", {
  getItem: () => "11111111-1111-4111-8111-111111111111", setItem() {},
}); });
afterEach(() => vi.unstubAllGlobals());

it('手工归类成功后本地卡片移动，失败保持原分类', async () => {
  const items = [{ ...original, category: null, wardrobe_group: 'unclassified' as const }];
  const patch = { wardrobe_group: 'jewelry' as const, sub: '项链' };
  const next = await saveWardrobeItem(items, original.id, patch, async (_, options) => {
    expect(JSON.parse(options?.body as string)).toEqual(patch);
    return Response.json({ ...items[0], ...patch });
  });
  expect(next[0].wardrobe_group).toBe('jewelry');
  expect(items[0].wardrobe_group).toBe('unclassified');
  await expect(saveWardrobeItem(items, original.id, patch, async () => Response.json({ detail: '分类保存失败' }, { status: 503 }))).rejects.toThrow('分类保存失败');
  expect(items[0].wardrobe_group).toBe('unclassified');
});

it("删除204无需解析JSON，成功才移除本地卡片并携带设备头", async () => {
  const { deleteWardrobeItem } = await import("./api");
  const items = [original, { ...original, id: "other" }];
  const next = await deleteWardrobeItem(items, original.id, async (path, options) => {
    expect(path).toBe("/api/wardrobe/items/W01");
    expect(options?.method).toBe("DELETE");
    expect(new Headers(options?.headers).get("X-Device-ID")).toBe(original.owner_id);
    return new Response(null, { status: 204 });
  });
  expect(next.map((item) => item.id)).toEqual(["other"]);
  expect(items.map((item) => item.id)).toEqual(["W01", "other"]);
});

it("删除失败保留原卡片并返回中文提示", async () => {
  const { deleteWardrobeItem } = await import("./api");
  const items = [original];
  await expect(deleteWardrobeItem(items, original.id, async () =>
    Response.json({ detail: "删除未完成，请稍后重试。" }, { status: 500 }))).rejects.toThrow("删除未完成");
  expect(items).toEqual([original]);
});

it("照片加载经过带设备头的API，解码失败立即释放URL，卸载不重复释放", async () => {
  const { watchWardrobePhoto } = await import("./api");
  const created = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:t15");
  const revoked = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const states: { status: string; url: string }[] = [];
  try {
    const photo = watchWardrobePhoto("W01", (state) => states.push(state), async (path, options) => {
      expect(path).toBe("/api/wardrobe/items/W01/photo");
      expect(new Headers(options?.headers).get("X-Device-ID")).toBe(original.owner_id);
      return new Response(new Blob(["photo"], { type: "image/jpeg" }));
    });
    expect(states[0]).toEqual({ status: "loading", url: "" });
    await vi.waitFor(() => expect(states.at(-1)).toEqual({ status: "ready", url: "blob:t15" }));
    photo.fail();
    expect(states.at(-1)).toEqual({ status: "error", url: "" });
    expect(revoked).toHaveBeenCalledExactlyOnceWith("blob:t15");
    photo.dispose();
    expect(revoked).toHaveBeenCalledTimes(1);
  } finally { created.mockRestore(); revoked.mockRestore(); }
});

it("照片卸载时释放URL，迟到响应不得再生成URL或更新已卸载页面", async () => {
  const { watchWardrobePhoto } = await import("./api");
  const created = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:t15");
  const revoked = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const states: { status: string; url: string }[] = [];
  try {
    const loaded = watchWardrobePhoto("W01", (state) => states.push(state), async () =>
      new Response(new Blob(["photo"], { type: "image/jpeg" })));
    await vi.waitFor(() => expect(states.at(-1)?.status).toBe("ready"));
    loaded.dispose();
    expect(revoked).toHaveBeenCalledExactlyOnceWith("blob:t15");
    let finish!: (response: Response) => void;
    const lateStates: { status: string; url: string }[] = [];
    const pending = watchWardrobePhoto("W01", (state) => lateStates.push(state), async () =>
      new Promise<Response>((resolve) => { finish = resolve; }));
    pending.dispose();
    finish(new Response(new Blob(["late"], { type: "image/jpeg" })));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(lateStates).toEqual([{ status: "loading", url: "" }]);
    expect(created).toHaveBeenCalledTimes(1);
  } finally { created.mockRestore(); revoked.mockRestore(); }
});

it("照片请求失败进入文字降级状态，不生成裂图URL", async () => {
  const { watchWardrobePhoto } = await import("./api");
  const states: { status: string; url: string }[] = [];
  const photo = watchWardrobePhoto("W01", (state) => states.push(state), async () =>
    Response.json({ detail: "照片不存在。" }, { status: 404 }));
  await vi.waitFor(() => expect(states.at(-1)).toEqual({ status: "error", url: "" }));
  photo.dispose();
});

const original: WardrobeItem = {
  id: "W01", owner_id: "11111111-1111-4111-8111-111111111111", name: null, image_path: null, category: "top", sub: "衬衫",
  colors: ["白色"], material: "棉", pattern: null, warmth: 2, formality: 3,
  seasons: ["spring"], confidence: 0.4, needs_confirm: true, user_edited: false,
  created_at: "2026-11-13T00:00:00Z", sources: { sub: "model", colors: "model" },
};

describe("衣柜状态与真实接口客户端", () => {
  it("loading 优先于已有列表和空列表", () => {
    expect(getViewState({ status: "loading", itemCount: 12 })).toBe("loading");
    expect(getViewState({ status: "loading", itemCount: 0 })).toBe("loading");
  });

  it("成功加载空衣柜进入 empty", async () => {
    const items = await getWardrobe(undefined, async () => Response.json([]));
    expect(getViewState({ status: "ok", itemCount: items.length })).toBe("empty");
  });

  it("PATCH 成功后用服务器结果本地更新，保留其他单品和原数组", async () => {
    const items = [original, { ...original, id: "W02" }];
    const updated = { ...original, sub: "白衬衫", user_edited: true, needs_confirm: false,
      sources: { ...original.sources, sub: "user" } };
    const next = await saveWardrobeItem(items, "W01", { sub: "白衬衫" }, async (url, options) => {
      expect(url).toBe("/api/wardrobe/items/W01");
      expect(options?.method).toBe("PATCH");
      expect(JSON.parse(options?.body as string)).toEqual({ sub: "白衬衫" });
      return Response.json(updated);
    });
    expect(next[0]).toEqual(updated);
    expect(next[1]).toBe(items[1]);
    expect(items[0].sub).toBe("衬衫");
  });

  it("PATCH 失败不改变原列表并保留中文错误", async () => {
    const items = [original];
    await expect(saveWardrobeItem(items, "W01", { sub: "x" }, async () =>
      Response.json({ detail: "单品不存在。" }, { status: 404 }),
    )).rejects.toThrow("单品不存在。");
    expect(items).toEqual([original]);
  });

  it("网络失败提供可读文案", async () => {
    await expect(getWardrobe(undefined, async () => { throw new TypeError("Failed to fetch"); }))
      .rejects.toThrow("连接失败");
  });

  it("上传失败保留同一File、draft_id与卡片占位，重试无需重新选图", async () => {
    const file = new File(["photo"], "cloth01.jpg", { type: "image/jpeg" });
    const draft = createPhotoDraft(file, "a032ac9e-3114-455b-8941-f2854d50f3c9");
    const states: PhotoDraft[] = [];
    const calls: FormData[] = [];
    const failure = await submitPhotoDraft(draft, (state) => states.push(state), async (path, options) => {
      expect(path).toBe("/api/wardrobe/items");
      expect(options?.method).toBe("POST");
      expect(new Headers(options?.headers).get("content-type")).toBeNull();
      expect(new Headers(options?.headers).get("X-Device-ID")).toBe(original.owner_id);
      calls.push(options?.body as FormData);
      return Response.json({ detail: "识别超时，图片已保留。请重试，或稍后再试。", category: "timeout" }, { status: 504 });
    });
    expect(failure).toBeNull();
    const retained = states[states.length - 1];
    expect(retained.file).toBe(file);
    expect(retained.id).toBe(draft.id);
    expect(retained.stage).toBe("error");
    expect(retained.error).toContain("请重试，或稍后再试");
    expect(hasUploadPlaceholder(retained)).toBe(true);
    expect(calls[0].get("photo")).toBe(file);
    expect(calls[0].get("draft_id")).toBe(draft.id);
    const result = await submitPhotoDraft(retained, (state) => states.push(state), async (_, options) => {
      calls.push(options?.body as FormData);
      return Response.json({ draft_id: draft.id, items: [original], corrections: [], latency_ms: 20,
        prompt_version: "item_extract.v2", reused: true });
    });
    expect(result?.items[0].id).toBe("W01");
    expect(calls[1].get("draft_id")).toBe(draft.id);
    expect(calls[1].get("photo")).toBe(file);
    expect(states[states.length - 1].stage).toBe("done");
    expect(hasUploadPlaceholder(states[states.length - 1])).toBe(false);
  });

  it("断网失败保留图片，不将错误藏成成功", async () => {
    const file = new File(["photo"], "photo.jpg", { type: "image/jpeg" });
    const states: PhotoDraft[] = [];
    expect(await submitPhotoDraft(createPhotoDraft(file, "draft"), (state) => states.push(state), async () => {
      throw new TypeError("Failed to fetch");
    })).toBeNull();
    expect(states[states.length - 1].file).toBe(file);
    expect(states[states.length - 1].error).toContain("图片已保留");
    expect(hasUploadPlaceholder(states[states.length - 1])).toBe(true);
  });

  it("上传成功合并到卡片墙，不重复插入幂等返回的ID或覆盖其他卡片", () => {
    const items = [original, { ...original, id: "W02" }];
    const updated = { ...original, sub: "确认后的衬衫" };
    const result = mergeWardrobeItems(items, [updated]);
    expect(result.map((item) => item.id)).toEqual(["W01", "W02"]);
    expect(result[0].sub).toBe("确认后的衬衫");
    expect(result[1]).toBe(items[1]);
    expect(items[0].sub).toBe("衬衫");
  });

  it("成功HTTP但返回空items也保留图片和占位", async () => {
    const draft = createPhotoDraft(new File(["photo"], "photo.jpg"), "draft");
    const states: PhotoDraft[] = [];
    expect(await submitPhotoDraft(draft, (state) => states.push(state), async () =>
      Response.json({ draft_id: draft.id, items: [] }),
    )).toBeNull();
    expect(states[states.length - 1].stage).toBe("error");
    expect(states[states.length - 1].file).toBe(draft.file);
  });

  it("POST先成功后旧GET才失败，不触发旧加载错误或隐藏新卡", async () => {
    const pendingLoad = new AbortController();
    let uploadRevision = 0;
    const startedRevision = uploadRevision;
    let rejectGet!: (reason: Error) => void;
    const deferred = new Promise<Response>((_, reject) => { rejectGet = reject; });
    const loaded: WardrobeItem[][] = [];
    const errors: string[] = [];
    const loading = loadWardrobe(pendingLoad.signal, (items) => loaded.push(items), (error) => errors.push(error),
      async () => deferred, () => uploadRevision === startedRevision);
    const draft = createPhotoDraft(new File(["photo"], "photo.jpg"), "draft");
    const result = await submitPhotoDraft(draft, () => {}, async () => Response.json({
      draft_id: draft.id, items: [original], corrections: [], latency_ms: 1,
      prompt_version: "item_extract.v2", reused: false,
    }), () => { uploadRevision += 1; });
    expect(result?.items).toEqual([original]);
    rejectGet(new TypeError("late network failure"));
    await loading;
    expect(errors).toEqual([]);
    expect(loaded).toEqual([]);
  });

  it("POST先成功后旧GET成功，保留新卡并补回原有衣柜", async () => {
    let resolveGet!: (response: Response) => void;
    const deferred = new Promise<Response>((resolve) => { resolveGet = resolve; });
    let uploadRevision = 0;
    let items: WardrobeItem[] = [];
    const startedRevision = uploadRevision;
    const errors: string[] = [];
    const loading = loadWardrobe(new AbortController().signal,
      (loaded) => { items = mergeWardrobeItems(loaded, items); }, (error) => errors.push(error),
      async () => deferred, () => uploadRevision === startedRevision);
    const draft = createPhotoDraft(new File(["photo"], "photo.jpg"), "draft");
    const added = { ...original, id: "new-item" };
    const result = await submitPhotoDraft(draft, () => {}, async () => Response.json({
      draft_id: draft.id, items: [added], corrections: [], latency_ms: 1,
      prompt_version: "item_extract.v2", reused: false,
    }), () => { uploadRevision += 1; });
    items = mergeWardrobeItems(items, result!.items);
    resolveGet(Response.json([original]));
    await loading;
    expect(items.map((item) => item.id)).toEqual(["new-item", "W01"]);
    expect(errors).toEqual([]);
  });
});

it("照片与JSON接口一样携带设备头，照片不放设备ID进URL", async () => {
  const { getWardrobePhoto } = await import("./api");
  const photo = await getWardrobePhoto("owned-photo", undefined, async (url, options) => {
    expect(url).toBe("/api/wardrobe/items/owned-photo/photo");
    expect(new Headers(options?.headers).get("X-Device-ID")).toBe("11111111-1111-4111-8111-111111111111");
    return new Response(new Blob(["photo"], { type: "image/jpeg" }));
  });
  expect(photo.type).toBe("image/jpeg");
});

it("拒绝衣柜返回其他设备单品", async () => {
  await expect(getWardrobe(undefined, async () => Response.json([{ ...original, owner_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" }])))
    .rejects.toThrow("归属");
});

it("清空只发送本设备DELETE，保留设备标识供当日配额使用", async () => {
  const { clearWardrobe } = await import("./api");
  const result = await clearWardrobe(async (_, options) => {
    expect(options?.method).toBe("DELETE");
    expect(new Headers(options?.headers).get("X-Device-ID")).toBe(original.owner_id);
    return Response.json({ wardrobe_items: 1, sessions: 1, outfit_sets: 3, outfit_items: 12, photos: 1 });
  });
  expect(result.wardrobe_items).toBe(1);
});

it("这是对的经显式确认接口清队列，不伪造属性编辑", async () => {
  const { confirmWardrobeItem } = await import("./api");
  const updated = { ...original, user_edited: true, needs_confirm: false };
  const result = await confirmWardrobeItem([original], original.id, async (url, options) => {
    expect(url).toBe("/api/wardrobe/items/W01/confirm");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
    expect(new Headers(options?.headers).get("X-Device-ID")).toBe(original.owner_id);
    return Response.json(updated);
  });
  expect(result[0]).toEqual(updated);
  expect(result[0].confidence).toBe(original.confidence);
  expect(result[0].sources).toEqual(original.sources);
  expect(original.needs_confirm).toBe(true);
});

it("确认失败保留原卡片待确认状态", async () => {
  const { confirmWardrobeItem } = await import("./api");
  await expect(confirmWardrobeItem([original], original.id, async () => Response.json({ detail: "请稍后重试。" }, { status: 500 })))
    .rejects.toThrow("重试");
  expect(original.needs_confirm).toBe(true);
});

it("编辑待确认单品但未改字段时保存，走确认而不是伪造category PATCH", async () => {
  const pending: WardrobeItem = { ...original, sources: { ...original.sources, category: "model" } };
  const confirmed = { ...pending, needs_confirm: false, user_edited: true };
  const result = await saveWardrobeItem([pending], pending.id, {}, async (url, options) => {
    expect(url).toBe("/api/wardrobe/items/W01/confirm");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
    return Response.json(confirmed);
  });
  expect(result[0].sources.category).toBe("model");
  expect(result[0].category).toBe(pending.category);
});

it("上传失败文案面向用户且保留重试草稿，不提未开放入口", async () => {
  const draft = createPhotoDraft(new File(["photo"], "photo.jpg"), "draft");
  const states: PhotoDraft[] = [];
  await submitPhotoDraft(draft, (next) => states.push(next), async () => { throw new TypeError("offline"); });
  const failed = states[states.length - 1];
  expect(failed.error).toContain("请重试，或稍后再试");
  expect(failed.error).not.toContain("手动建档");
  expect(failed.file).toBe(draft.file);
});
