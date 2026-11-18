import { bodyShapes } from '../components/BodyShapeGuide';
import type { BodyShape } from '../components/BodyShapeGuide';
import { deviceHeaders, getDeviceId } from './deviceId';

export type ProfileInput = { height_cm: number | null; weight_kg: number | null; body_shape: BodyShape | null };
export type OwnedProfile = ProfileInput & { owner_id: string };
export type ProfileDraft = { height: string; weight: string; shape: BodyShape | '' };

export function parseProfileDraft(draft: { height: string; weight: string; shape: string }): ProfileInput {
  function number(text: string, label: string) {
    if (!text.trim()) return null;
    const value = Number(text);
    if (!Number.isFinite(value) || value <= 0) throw new Error(`请输入大于0的${label}数字。`);
    return value;
  }
  if (draft.shape && !bodyShapes.some(shape => shape.id === draft.shape)) throw new Error('请选择提供的五种体型之一。');
  return { height_cm: number(draft.height, '身高'), weight_kg: number(draft.weight, '体重'), body_shape: draft.shape as BodyShape || null };
}

async function profileRequest(options: RequestInit, fetcher: typeof fetch, owner: string): Promise<OwnedProfile> {
  if (getDeviceId() !== owner) throw new Error('设备标识已变化，请重新加载资料后保存。');
  const timeout = AbortSignal.timeout(10000);
  let response: Response;
  try { response = await fetcher('/api/profile', { ...options, headers: deviceHeaders(options.headers), signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout }); }
  catch { throw new Error('身材资料连接失败，请重试。'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('资料响应格式有误，请重试。'); }
  if (getDeviceId() !== owner) throw new Error('设备标识已变化，请重新加载资料。');
  if (!data || typeof data !== 'object') throw new Error('资料响应字段有误，请重试。');
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '资料保存失败，请重试。');
  if (data.owner_id !== owner) throw new Error('资料归属不一致，请重新加载。');
  for (const field of ['height_cm', 'weight_kg'] as const) {
    if (data[field] !== null && (typeof data[field] !== 'number' || !Number.isFinite(data[field]) || data[field] <= 0)) throw new Error('资料响应字段有误，请重试。');
  }
  if (data.body_shape !== null && !bodyShapes.some(shape => shape.id === data.body_shape)) throw new Error('体型响应有误，请重试。');
  return data;
}

export function getProfile(signal?: AbortSignal, fetcher: typeof fetch = fetch) {
  return profileRequest({ signal }, fetcher, getDeviceId());
}

export function saveProfile(input: ProfileInput, fetcher: typeof fetch = fetch, owner = getDeviceId()) {
  return profileRequest({ method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(input) }, fetcher, owner);
}
