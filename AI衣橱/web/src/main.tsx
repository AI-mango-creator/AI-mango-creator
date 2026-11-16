import { Component, lazy, StrictMode, Suspense } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const App = lazy(() => import("./App"));

class StartupBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="shell">
          <section className="panel" role="alert">
            <h1 className="text-xl font-semibold">页面暂时无法加载</h1>
            <p className="mt-3 text-sm text-slate-600">
              请检查连接，然后重新加载页面。
            </p>
            <button
              className="mt-5 rounded-xl bg-slate-800 px-5 py-3 text-sm text-white"
              onClick={() => window.location.reload()}
              type="button"
            >
              重新加载
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("页面缺少挂载节点，请重新加载。");
}

createRoot(root).render(
  <StrictMode>
    <StartupBoundary>
      <Suspense
        fallback={
          <main className="shell">
            <section className="panel" role="status">
              <p className="text-sm text-slate-600">正在加载算法衣橱…</p>
              <div className="mt-5 h-5 w-2/3 animate-pulse rounded bg-slate-200" />
              <div className="mt-3 h-20 animate-pulse rounded-xl bg-slate-100" />
            </section>
          </main>
        }
      >
        <App />
      </Suspense>
    </StartupBoundary>
  </StrictMode>,
);
