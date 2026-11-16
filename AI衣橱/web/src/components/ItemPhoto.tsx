import { useEffect, useRef, useState } from "react";
import { categoryLabels, watchWardrobePhoto } from "../lib/api";
import type { ItemPhotoState, WardrobeItem } from "../lib/api";

export default function ItemPhoto({ item }: { item: WardrobeItem }) {
  const [photo, setPhoto] = useState<ItemPhotoState>({ status: "loading", url: "" });
  const resource = useRef<ReturnType<typeof watchWardrobePhoto> | null>(null);
  useEffect(() => {
    if (!item.image_path) { setPhoto({ status: "error", url: "" }); return; }
    const current = watchWardrobePhoto(item.id, setPhoto);
    resource.current = current;
    return () => { current.dispose(); resource.current = null; };
  }, [item.id, item.image_path]);
  const label = `${item.category ? categoryLabels[item.category] : "品类待确认"} · ${item.sub || "子类待确认"}`;
  return photo.status === "ready" && item.image_path ?
    <img src={photo.url} alt={label} className="aspect-square w-full rounded-xl bg-slate-100 object-cover"
      onError={() => resource.current?.fail()} /> :
    <span data-photo-state={item.image_path ? photo.status : "error"}
      className={`flex aspect-square w-full min-w-0 items-center justify-center break-all rounded-xl bg-slate-100 p-2 text-center text-xs leading-5 text-slate-500 ${photo.status === "loading" && item.image_path ? "animate-pulse" : ""}`}>
      {photo.status === "loading" && item.image_path ? "照片加载中…" : label}
    </span>;
}
