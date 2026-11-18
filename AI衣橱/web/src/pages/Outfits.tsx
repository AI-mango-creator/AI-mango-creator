import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import DegradeBanner from "../components/DegradeBanner";
import ItemPhoto from "../components/ItemPhoto";
import AppIcon from "../components/AppIcon";
import type { WeatherSelection } from "../lib/weatherApi";
import { categoryLabels } from "../lib/api";
import { createOutfits, occasionLabels } from "../lib/outfitsApi";
import type { OutfitsInput, OutfitsResult } from "../lib/outfitsApi";
import { getViewState } from "../lib/viewState";

const fieldClass = "mt-2 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3 py-2 text-base";
const previewSlots = ["top", "bottom", "shoes", "outer", "dress", "accessory"];

export default function Outfits({ initialWeather, onBack }: { initialWeather?: WeatherSelection | null; onBack?: () => void }) {
  const [temp, setTemp] = useState(initialWeather ? String(initialWeather.temperature) : "18");
  const [occasion, setOccasion] = useState<OutfitsInput["occasion"]>("commute");
  const [status, setStatus] = useState<"loading" | "error" | "ok">("ok");
  const [result, setResult] = useState<OutfitsResult | null>(null);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const state = getViewState({ status, itemCount: result?.sets.length ?? 0 });
  useEffect(() => () => request.current?.abort(), []);

  async function generate(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const temperature = Number(temp);
    if (temp.trim() === "" || !Number.isInteger(temperature)) {
      setError("请输入整数温度。"); setStatus("error"); return;
    }
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setStatus("loading");
    setError("");
    try {
      const next = await createOutfits({ temp_c: temperature, occasion }, controller.signal);
      if (!controller.signal.aborted) { setResult(next); setStatus("ok"); }
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(failure instanceof Error ? failure.message : "搭配生成失败，请重试。");
        setStatus("error");
      }
    }
  }

  return <main className="shell outfits-page">
    {state === "ready" && result?.degraded && <DegradeBanner key={result.session_id} reason={result.degrade_reason} />}
    <header className="detail-header"><button aria-label="返回衣橱" onClick={onBack}><AppIcon name="back" /></button><h1>AI帮我搭</h1><span /></header>
    <div className="outfits-intro"><span className="eyebrow">YOUR CLOSET. YOUR STYLE.</span><h2>今天，穿出自己的样子</h2><p>只从你的衣橱里，挑选真正能穿出门的搭配。</p></div>
    {initialWeather && <p className="weather-source">⌖ {initialWeather.city} · {initialWeather.date} 预报最低温 {initialWeather.temperature}°C<br /><small>已带入参考温度，可按出门时间手动修改。</small></p>}
    <form onSubmit={generate} className="panel mb-5">
      <fieldset disabled={status === "loading"} className="min-w-0">
        <div className="grid min-w-0 grid-cols-2 gap-3">
          <label className="min-w-0 text-sm">今天温度（℃）
            <input className={fieldClass} type="number" step="1" required value={temp} onChange={(event) => setTemp(event.target.value)} />
          </label>
          <label className="min-w-0 text-sm">出门场合
            <select className={fieldClass} value={occasion} onChange={(event) => setOccasion(event.target.value as OutfitsInput["occasion"])}>
              {Object.entries(occasionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
        <button className="gradient-button mt-5 w-full" type="submit">
          {status === "loading" ? "正在生成…" : "生成搭配"}
        </button>
      </fieldset>
    </form>
    {state === "loading" && <section className="panel" role="status">
      <h2 className="font-semibold">正在挑选今天的搭配…</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">正在检查衣柜、温度和场合，请稍候。</p>
      <div className="mt-4 space-y-2" aria-hidden="true">
        {[1, 2, 3].map((key) => <div key={key} className="h-8 animate-pulse rounded-lg bg-slate-200" />)}
      </div>
    </section>}
    {state === "error" && <section className="panel" role="alert">
      <h2 className="font-semibold">本次搭配暂时无法生成</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">{error}</p>
      <button className="mt-4 rounded-xl bg-slate-800 px-4 py-3 text-sm text-white" type="button" onClick={() => void generate()}>重新生成</button>
    </section>}
    {state === "empty" && <section className="panel">
      <h2 className="font-semibold">{result ? "今天还缺几件合适的单品" : "先选好今天的温度和场合"}</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">{result?.shortage_hint ?? "点击生成搭配，看看衣柜里有哪些能直接穿出门的组合。"}</p>
      {result?.shortage && <ul className="mt-3 space-y-2 text-sm">
        {Object.entries(result.shortage).map(([slot, requirement]) => <li key={slot}>
          缺少{categoryLabels[slot as keyof typeof categoryLabels] ?? "单品"}：厚薄至少 {requirement.warmth_min}，正式度至少 {requirement.formality_min}。
        </li>)}
      </ul>}
    </section>}
    {state === "ready" && result && <>
      <p className="mb-4 text-sm text-slate-600">共 {result.sets.length} 套{result.degraded ? "基础搭配" : "搭配"}</p>
      <section aria-label="搭配方案" className="space-y-4">
        {result.sets.map((outfit) => <article key={outfit.id} className="panel min-w-0">
          <h2 className="text-lg font-semibold">方案 {outfit.rank}</h2>
          <ul className="mt-3 grid min-w-0 grid-cols-3 gap-2 text-xs leading-5">
            {previewSlots.flatMap((slot) => {
              const item = outfit.items.find((value) => value.id === outfit.slots[slot]);
              return item ? [<li key={slot} className="min-w-0">
                <ItemPhoto item={item} />
                <span className="mt-2 block text-slate-500">{categoryLabels[slot as keyof typeof categoryLabels]}</span>
                <span className="block break-all">{item.category ? categoryLabels[item.category] : "品类待确认"} · {item.sub || item.name || "子类待确认"}</span>
                <span className="block break-all text-slate-500">{item.colors.join(" / ") || "颜色未标注"}</span>
              </li>] : [];
            })}
          </ul>
          <p className="mt-4 border-t border-slate-200 pt-3 text-sm leading-6 text-slate-700">{outfit.reason}</p>
        </article>)}
      </section>
      {result.shortage_hint && <p className="mt-4 text-sm leading-6 text-slate-600">{result.shortage_hint}</p>}
    </>}
  </main>;
}
