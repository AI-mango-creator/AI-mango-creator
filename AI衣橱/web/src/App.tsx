import { useState } from "react";
import Outfits from "./pages/Outfits";
import Wardrobe from "./pages/Wardrobe";
import Profile from "./pages/Profile";

export default function App() {
  const [page, setPage] = useState<"wardrobe" | "outfits" | "profile">("wardrobe");
  return <>
    <nav aria-label="页面切换" className="mx-auto flex w-full max-w-[480px] flex-wrap gap-2 px-4 pt-5">
      <button type="button" className={`rounded-xl px-4 py-2 text-sm ${page === "wardrobe" ? "bg-slate-800 text-white" : "bg-white"}`} onClick={() => setPage("wardrobe")}>我的衣柜</button>
      <button type="button" className={`rounded-xl px-4 py-2 text-sm ${page === "outfits" ? "bg-slate-800 text-white" : "bg-white"}`} onClick={() => setPage("outfits")}>今天怎么穿</button>
      <button type="button" className={`rounded-xl px-4 py-2 text-sm ${page === "profile" ? "bg-slate-800 text-white" : "bg-white"}`} onClick={() => setPage("profile")}>身材资料</button>
    </nav>
    {page === "wardrobe" ? <Wardrobe /> : page === "outfits" ? <Outfits /> : <Profile />}
  </>;
}
