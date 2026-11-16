import { describe, expect, it } from "vitest";
import { getDeviceId, deviceHeaders } from "./deviceId";

function storage(value: string | null = null) {
  const values = new Map<string, string>(value === null ? [] : [["wardrobe.device_id", value]]);
  return { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, next: string) => { values.set(key, next); } };
}

describe("唯一设备身份模块", () => {
  it("生成一次并持久化，同一存储重复读取稳定", () => {
    const local = storage();
    const first = getDeviceId(local);
    expect(first).toMatch(/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/);
    expect(getDeviceId(local)).toBe(first);
    expect(local.getItem("wardrobe.device_id")).toBe(first);
  });
  it("替换legacy和非法标识，规范化已有UUID", () => {
    expect(getDeviceId(storage("legacy"))).not.toBe("legacy");
    expect(getDeviceId(storage("broken"))).not.toBe("broken");
    expect(getDeviceId(storage("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"))).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
  });
  it("存储拒绝时给中文错误，不悄悄生成每次不同的设备", () => {
    expect(() => getDeviceId({ getItem() { throw new Error("denied"); }, setItem() {} })).toThrow("本地存储");
  });
  it("统一设备请求头保留原Content-Type", () => {
    const local = storage("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    const result = deviceHeaders({ "content-type": "application/json" }, local);
    expect(result.get("X-Device-ID")).toBe(getDeviceId(local));
    expect(result.get("content-type")).toBe("application/json");
  });
});
