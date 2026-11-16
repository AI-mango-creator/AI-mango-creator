import { describe, expect, it } from "vitest";
import { getViewState } from "./viewState";

describe("getViewState", () => {
  it("loading 先返回，不落入 error 或数量判断分支", () => {
    expect(getViewState({ status: "loading", itemCount: 0 })).toBe("loading");
    expect(getViewState({ status: "loading", itemCount: 3 })).toBe("loading");
  });

  it("error 优先于 empty", () => {
    expect(getViewState({ status: "error", itemCount: 0 })).toBe("error");
  });

  it("ok 且 0 件时返回 empty", () => {
    expect(getViewState({ status: "ok", itemCount: 0 })).toBe("empty");
  });

  it("ok 且 3 件时返回 ready", () => {
    expect(getViewState({ status: "ok", itemCount: 3 })).toBe("ready");
  });
});
