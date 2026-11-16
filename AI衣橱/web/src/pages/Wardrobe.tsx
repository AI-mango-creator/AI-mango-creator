import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { categoryLabels, confirmWardrobeItem, createPhotoDraft, deleteWardrobeItem, hasUploadPlaceholder, loadWardrobe, mergeWardrobeItems,
  saveWardrobeItem, submitPhotoDraft } from "../lib/api";
import type { Category, PhotoDraft, WardrobeItem, WardrobePatch } from "../lib/api";
import ItemPhoto from "../components/ItemPhoto";
import { getViewState } from "../lib/viewState";

type Draft = { sub: string; colors: string; material: string; pattern: string; category: Category | "" };
const inputClass = "mt-1 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3 py-2 text-base";
const buttonClass = "rounded-xl bg-slate-800 px-4 py-3 text-sm text-white disabled:opacity-50";

export default function Wardrobe() {
  const [items, setItems] = useState<WardrobeItem[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "ok">("loading");
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState<WardrobeItem | null>(null);
  const [draft, setDraft] = useState<Draft>({ sub: "", colors: "", material: "", pattern: "", category: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<WardrobeItem | null>(null);
  const removedIds = useRef(new Set<string>());
  const [saveError, setSaveError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [photoDraft, setPhotoDraft] = useState<PhotoDraft | null>(null);
  const [preview, setPreview] = useState("");
  const [highlighted, setHighlighted] = useState<string[]>([]);
  const photoInput = useRef<HTMLInputElement>(null);
  const uploadRevision = useRef(0);
  const highlightTimer = useRef<number | null>(null);
  const uploading = photoDraft?.stage === "uploading";
  const busy = saving || uploading || deleting;
  const state = getViewState({ status, itemCount: items.length });

  useEffect(() => {
    const controller = new AbortController();
    const revision = uploadRevision.current;
    setStatus("loading");
    void loadWardrobe(controller.signal,
      (loaded) => { setItems((current) => mergeWardrobeItems(loaded.filter((item) => !removedIds.current.has(item.id)), current)); setStatus("ok"); },
      (message) => { setLoadError(message); setStatus("error"); }, undefined,
      () => uploadRevision.current === revision);
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!photoDraft?.file) return;
    const url = URL.createObjectURL(photoDraft.file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photoDraft?.file]);

  useEffect(() => () => {
    if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
  }, []);

  async function upload(draft: PhotoDraft) {
    if (busy) return;
    setNotice("");
    const result = await submitPhotoDraft(draft, setPhotoDraft, undefined, () => { uploadRevision.current += 1; });
    if (result) {
      setItems((current) => mergeWardrobeItems(current, result.items));
      setStatus("ok");
      setHighlighted(result.items.map((item) => item.id));
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
      highlightTimer.current = window.setTimeout(() => setHighlighted([]), 2000);
      setNotice(`已建档 ${result.items.length} 件${result.corrections.length ? `，已记录 ${result.corrections.length} 项校正` : ""}。`);
      if (photoInput.current) photoInput.current.value = "";
    }
  }

  async function confirm(item: WardrobeItem) {
    if (busy) return;
    setSaving(true);
    setNotice("");
    setActionError("");
    try {
      const updated = (await confirmWardrobeItem(items, item.id)).find((value) => value.id === item.id);
      if (updated) setItems((current) => current.map((value) => value.id === item.id ? updated : value));
      if (editing?.id === item.id) setEditing(null);
      setNotice("已确认，衣柜已更新。");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "确认失败，请重试。");
    } finally { setSaving(false); }
  }

  function edit(item: WardrobeItem) {
    setEditing(item);
    setDraft({ sub: item.sub ?? "", colors: item.colors.join("，"), material: item.material ?? "",
      pattern: item.pattern ?? "", category: item.category ?? "" });
    setSaveError("");
    setNotice("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || busy) return;
    const patch: WardrobePatch = {};
    for (const field of ["sub", "material", "pattern"] as const) {
      const value = draft[field].trim() || null;
      if (value !== editing[field]) patch[field] = value;
    }
    const colors = draft.colors.split(/[,，、]/).map((value) => value.trim()).filter(Boolean);
    if (JSON.stringify(colors) !== JSON.stringify(editing.colors)) patch.colors = colors;
    if (draft.category && draft.category !== editing.category) patch.category = draft.category;
    if (Object.keys(patch).length === 0 && !editing.needs_confirm) { setSaveError("请先修改至少一项内容。"); return; }
    setSaving(true);
    setSaveError("");
    try {
      const updated = (await saveWardrobeItem(items, editing.id, patch)).find((item) => item.id === editing.id);
      if (updated) setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditing(null);
      setNotice("已保存，衣柜已更新。");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "保存失败，请重试。");
    } finally { setSaving(false); }
  }

  async function remove() {
    if (!pendingDelete || busy) return;
    const id = pendingDelete.id;
    setDeleting(true);
    setActionError("");
    setNotice("");
    try {
      await deleteWardrobeItem(items, id);
      removedIds.current.add(id);
      uploadRevision.current += 1;
      setItems((current) => current.filter((item) => item.id !== id));
      if (editing?.id === id) setEditing(null);
      setPendingDelete(null);
      setNotice("已删除单品，并移除历史方案中的引用。");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除失败，请稍后重试。");
    } finally { setDeleting(false); }
  }

  return (
    <main className="shell">
      <header className="mb-6">
        <p className="text-xs font-medium tracking-widest text-slate-500">WARDROBE COPILOT</p>
        <h1 className="mt-3 text-3xl font-semibold">我的衣柜</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">点开单品，修正识别结果。</p>
      </header>
      {pendingDelete && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 p-6">
        <section role="alertdialog" aria-modal="true" aria-label="删除单品确认" className="panel w-full min-w-0 max-w-[420px]">
          <h2 className="text-lg font-semibold">删除{pendingDelete.sub || "这件单品"}？</h2>
          <p className="mt-3 text-sm leading-6">删除后将从历史方案中移除，不可恢复</p>
          {actionError && <p role="alert" className="mt-3 text-sm leading-6 text-red-900">{actionError}</p>}
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" disabled={deleting} className={`${buttonClass} bg-red-800`} onClick={() => void remove()}>
              {deleting ? "正在删除…" : "确认删除"}
            </button>
            <button type="button" disabled={deleting} className="rounded-xl px-4 py-3 text-sm disabled:opacity-50" onClick={() => setPendingDelete(null)}>取消</button>
          </div>
        </section>
      </div>}
      <section aria-label="拍照建档" className="panel mb-5 min-w-0" data-upload-zone
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const file = event.dataTransfer.files[0];
          if (file && !busy) void upload(createPhotoDraft(file));
        }}>
        <h2 className="text-lg font-semibold">添加衣物照片</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">选择或拖入一张 JPG、PNG、WebP 图片（不超过10MB），识别后自动建档。</p>
        <label className="mt-3 block min-w-0 text-sm">选择照片
          <input ref={photoInput} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy}
            className="mt-2 block w-full min-w-0 max-w-full text-sm" onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(createPhotoDraft(file));
            }} />
        </label>
        {hasUploadPlaceholder(photoDraft) && photoDraft && <div data-upload-placeholder data-draft-id={photoDraft.id}
          className={`mt-4 min-w-0 rounded-xl border p-3 ${uploading ? "animate-pulse border-slate-200 bg-slate-50" : "border-red-200 bg-red-50"}`}>
          {preview && <img src={preview} alt="待建档照片预览" className="h-28 w-full rounded-lg object-contain" />}
          <p className="mt-2 break-all text-xs text-slate-600">{photoDraft.file.name}</p>
          {uploading ? <div role="status" className="mt-3">
            <div className="h-3 w-3/4 rounded bg-slate-200" />
            <p className="mt-3 text-sm">正在识别并保存衣物…</p>
          </div> : <div>
            <p role="alert" className="mt-3 text-sm leading-6 text-red-900">{photoDraft.error}</p>
            <p className="mt-2 text-xs leading-5 text-slate-600">照片已保留，不用重新选择。请重试，或稍后再试。</p>
            <button type="button" className={`${buttonClass} mt-3`} onClick={() => void upload(photoDraft)}>原地重试</button>
          </div>}
        </div>}
      </section>
      {actionError && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{actionError}</p>}
      {notice && <p role="status" className="mb-4 rounded-xl bg-green-50 p-3 text-sm text-green-900">{notice}</p>}
      {state === "loading" && <section className="panel" role="status">
        <h2 className="text-xl font-semibold">正在加载衣柜…</h2>
        <p className="mt-3 text-sm text-slate-600">正在读取你的单品，请稍候。</p>
      </section>}
      {state === "error" && <section className="panel" role="alert">
        <h2 className="text-xl font-semibold">衣柜暂时无法加载</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">{loadError}</p>
        <button type="button" className={`${buttonClass} mt-5`} onClick={() => setReload((value) => value + 1)}>重新加载</button>
      </section>}
      {state === "empty" && <section className="panel">
        <h2 className="text-xl font-semibold">衣柜里还没有单品</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">从上方选择或拖入一张衣物照片，识别后会出现在这里。</p>
      </section>}
      {state === "ready" && <>
        <p className="mb-4 text-sm text-slate-600">共 {items.length} 件 · 点击编辑</p>
        {editing && <section className="panel mb-5 min-w-0" aria-label="编辑单品">
          <h2 className="mb-2 text-lg font-semibold">编辑单品</h2>
          <p className="mb-4 break-all text-xs text-slate-500">ID：{editing.id}</p>
          {editing.confidence !== null && <p className="mb-4 text-xs text-slate-600">模型置信度 {Math.round(editing.confidence * 100)}%（仅供参考）</p>}
          <form onSubmit={save}>
            <fieldset disabled={busy} className="min-w-0 space-y-3">
              <label className="block text-sm">品类
                <select className={inputClass} value={draft.category} onChange={(event) => setDraft({ ...draft, category: event.target.value as Category })}>
                  <option value="" disabled>请选择品类</option>
                  {Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="block text-sm">子类
                <input className={inputClass} value={draft.sub} onChange={(event) => setDraft({ ...draft, sub: event.target.value })} />
              </label>
              <label className="block text-sm">颜色（多色用逗号分开）
                <input className={inputClass} value={draft.colors} onChange={(event) => setDraft({ ...draft, colors: event.target.value })} />
              </label>
              <label className="block text-sm">材质
                <input className={inputClass} value={draft.material} onChange={(event) => setDraft({ ...draft, material: event.target.value })} />
              </label>
              <label className="block text-sm">图案
                <input className={inputClass} value={draft.pattern} onChange={(event) => setDraft({ ...draft, pattern: event.target.value })} />
              </label>
              {saveError && <p role="alert" className="text-sm leading-6 text-red-800">{saveError}</p>}
              <div className="flex flex-wrap gap-3 pt-2">
                <button className={buttonClass} type="submit">{saving ? "正在保存…" : editing.needs_confirm ? "确认并保存" : "保存修改"}</button>
                <button type="button" className="px-3 py-3 text-sm" onClick={() => setEditing(null)}>取消</button>
              </div>
            </fieldset>
          </form>
        </section>}
        <section aria-label="衣柜单品" className="grid min-w-0 grid-cols-2 gap-3">
          {items.map((item) => <article key={item.id}
            data-item-id={item.id} data-highlighted={highlighted.includes(item.id) ? "true" : "false"}
            className={`min-w-0 rounded-2xl border bg-white p-3 text-left disabled:opacity-50 ${highlighted.includes(item.id) ? "border-green-500 ring-2 ring-green-300" : "border-slate-200"}`}
            >
            <div className="mb-2 flex justify-end">
              <button type="button" disabled={busy} aria-label={`删除${item.sub || "单品"}`}
                className="rounded-lg px-2 py-1 text-xs text-red-800 disabled:opacity-50"
                onClick={() => { setActionError(""); setPendingDelete(item); }}>删除</button>
            </div>
            <button type="button" className="block w-full min-w-0 text-left disabled:opacity-50" disabled={busy} onClick={() => edit(item)}>
            <ItemPhoto item={item} />
            <span className="mt-3 block break-all text-xs text-slate-500">{item.category ? categoryLabels[item.category] : "品类待确认"} · {item.sub || "子类待确认"}</span>
            <span className="mt-1 block font-semibold">{item.sub || item.name || "未命名单品"}</span>
            <span className="mt-2 block text-xs leading-5 text-slate-600">{item.colors.join(" / ") || "颜色待补充"}</span>
            {item.needs_confirm && <span className="mt-2 block text-xs text-amber-800">待确认</span>}
            {item.user_edited && <span className="mt-2 block text-xs text-green-800">已确认</span>}
            </button>
            {item.needs_confirm && <button type="button" disabled={busy} className={`${buttonClass} mt-3 w-full`}
              onClick={() => void confirm(item)}>这是对的</button>}
          </article>)}
        </section>
      </>}
    </main>
  );
}
