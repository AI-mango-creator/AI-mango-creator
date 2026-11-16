type DeviceStorage = Pick<Storage, "getItem" | "setItem">;
const storageKey = "wardrobe.device_id";
const uuidPattern = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;

export class DeviceIdError extends Error {}

// 原生封装时只替换这个模块的存储适配；组件和API均不直接接触localStorage。
export function getDeviceId(storage?: DeviceStorage): string {
  try {
    const local = storage ?? globalThis.localStorage;
    const saved = local.getItem(storageKey);
    const id = saved && uuidPattern.test(saved) ? saved.toLowerCase() : crypto.randomUUID();
    if (saved !== id) local.setItem(storageKey, id);
    return id;
  } catch {
    throw new DeviceIdError("无法保存设备标识，请允许本地存储后重试。");
  }
}

export function deviceHeaders(initial?: HeadersInit, storage?: DeviceStorage): Headers {
  const headers = new Headers(initial);
  headers.set("X-Device-ID", getDeviceId(storage));
  return headers;
}
