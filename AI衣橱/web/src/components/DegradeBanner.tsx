import { useState } from "react";
import type { DegradeReason } from "../lib/outfitsApi";

const messages: Record<DegradeReason, string> = {
  auth: "AI 服务暂不可用，请稍后再试",
  rate_limit: "AI 正忙，已为你用基础规则搭配",
  timeout: "AI 响应超时，已为你用基础规则搭配",
  parse_failed: "这次没生成好，已换成基础搭配。",
};

export default function DegradeBanner({ reason }: { reason: DegradeReason | null }) {
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <aside role="status" aria-label="基础搭配提示" className="mb-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold">以下为基础搭配</h2>
        <button type="button" className="shrink-0 text-sm underline" aria-label="关闭基础搭配提示" onClick={() => setClosed(true)}>关闭</button>
      </div>
      <p className="mt-2 text-sm leading-6">{reason ? messages[reason] : "AI 暂不可用，以下为基础搭配。"}</p>
    </aside>
  );
}
