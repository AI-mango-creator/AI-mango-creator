import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createOutfits } from "./outfitsApi";
const owner = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
beforeEach(() => { vi.stubGlobal("localStorage", { getItem: () => owner, setItem() {} }); });
afterEach(() => vi.unstubAllGlobals());
const input = { temp_c: 18, occasion: "commute" as const };
const result = { session_id: "S1", sets: [], shortage: { top: { slot: "top", warmth_min: 2, formality_min: 3 } },
  shortage_hint: "缺上装", degraded: false, degrade_reason: null, prompt_version: "outfit_compose.v1", latency_ms: 10 };

describe("编排携带统一设备身份", () => {
  it("编排请求同一设备头，保留输入与缺件返回", async () => {
    expect(await createOutfits(input, undefined, async (url, options) => {
      expect(url).toBe("/api/outfits");
      expect(new Headers(options?.headers).get("X-Device-ID")).toBe(owner);
      expect(JSON.parse(options?.body as string)).toEqual(input);
      return Response.json(result);
    })).toEqual(result);
  });
  it("429保留中文配额提示", async () => {
    await expect(createOutfits(input, undefined, async () => Response.json({ detail: "今日生成搭配已达30次上限，请明天再试。" }, { status: 429 })))
      .rejects.toThrow("30次上限");
  });
  it("拒绝包含其他设备单品的响应", async () => {
    await expect(createOutfits(input, undefined, async () => Response.json({ ...result,
      sets: [{ id: "set", items: [{ id: "foreign", owner_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" }] }],
    }))).rejects.toThrow("归属");
  });
});
