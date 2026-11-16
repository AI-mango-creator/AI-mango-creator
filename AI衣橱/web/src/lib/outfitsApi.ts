import { DeviceIdError, deviceHeaders, getDeviceId } from "./deviceId";
import type { WardrobeItem } from "./api";

export const occasionLabels = { commute: "通勤", date: "约会", weekend: "周末", client_meeting: "客户会议" } as const;
export type DegradeReason = "auth" | "rate_limit" | "timeout" | "parse_failed";
export type OutfitsInput = {
  temp_c: number;
  occasion: keyof typeof occasionLabels;
  formality_target?: [number, number];
  excluded?: string[];
};
export type OutfitsResult = {
  session_id: string;
  sets: { id: string; rank: number; slots: Record<string, string | null>; reason: string; items: WardrobeItem[] }[];
  shortage: Record<string, { slot: string; warmth_min: number; formality_min: number }> | null;
  shortage_hint: string | null;
  degraded: boolean;
  degrade_reason: DegradeReason | null;
  prompt_version: string;
  latency_ms: number;
};

export async function createOutfits(input: OutfitsInput, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<OutfitsResult> {
  const deadline = AbortSignal.timeout(70000);
  let response: Response;
  try {
    response = await fetcher("/api/outfits", {
      method: "POST", headers: deviceHeaders({ "content-type": "application/json" }), body: JSON.stringify(input),
      signal: signal ? AbortSignal.any([signal, deadline]) : deadline,
    });
  } catch (error) {
    if (signal?.aborted || error instanceof DeviceIdError) throw error;
    throw new Error(deadline.aborted ? "本次生成等待过久，请重试。" : "连接失败，请检查服务是否启动后重试。");
  }
  let payload: unknown;
  try { payload = await response.json(); }
  catch { throw new Error("服务响应格式有误，请重新生成。"); }
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
    throw new Error(typeof detail === "string" && /[\u4e00-\u9fff]/.test(detail)
      ? detail : "暂时无法生成搭配，请稍后重试。");
  }
  if (!payload || typeof payload !== "object" || !("sets" in payload) || !Array.isArray(payload.sets)
    || !("session_id" in payload) || typeof payload.session_id !== "string"
    || !("degraded" in payload) || typeof payload.degraded !== "boolean"
    || !("degrade_reason" in payload) || !("prompt_version" in payload)) {
    throw new Error("搭配响应字段不完整，请重新生成。");
  }
  const owner = getDeviceId();
  if (payload.sets.some((set) => !set || !Array.isArray(set.items) || set.items.some((item: WardrobeItem) => item.owner_id !== owner))) {
    throw new Error("搭配单品归属不一致，请重新生成。");
  }
  return payload as OutfitsResult;
}
