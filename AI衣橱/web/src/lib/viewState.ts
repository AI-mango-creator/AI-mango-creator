export function getViewState(input: {
  status: "loading" | "error" | "ok";
  itemCount: number;
}): "loading" | "error" | "empty" | "ready" {
  if (input.status === "loading") {
    return "loading";
  }
  if (input.status === "error") {
    return "error";
  }
  return input.itemCount === 0 ? "empty" : "ready";
}
