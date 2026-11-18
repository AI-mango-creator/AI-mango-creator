import { afterEach, describe, expect, it, vi } from 'vitest';
import { bodyShapes } from '../components/BodyShapeGuide';
import { getProfile, parseProfileDraft, saveProfile } from './profileApi';

afterEach(() => vi.unstubAllGlobals());

describe('身材资料', () => {
  it('保留单位对应数字和小数，空输入为null', () => {
    expect(parseProfileDraft({ height: '165.5', weight: '55.2', shape: 'A' })).toEqual({ height_cm: 165.5, weight_kg: 55.2, body_shape: 'A' });
    expect(parseProfileDraft({ height: '', weight: ' ', shape: '' })).toEqual({ height_cm: null, weight_kg: null, body_shape: null });
  });
  it('拒绝负数、非有限数和不在五型中的值', () => {
    for (const value of ['-1', '0', 'NaN', 'Infinity', 'abc']) {
      expect(() => parseProfileDraft({ height: value, weight: '', shape: '' })).toThrow();
    }
    expect(() => parseProfileDraft({ height: '', weight: '', shape: 'Q' })).toThrow();
  });
  it('提供五个有区分的示意和用户指定描述', () => {
    expect(bodyShapes.map(x => x.id)).toEqual(['X', 'A', 'TY', 'H', 'O']);
    expect(new Set(bodyShapes.map(x => x.outline)).size).toBe(5);
    expect(bodyShapes[2].description).toContain('肩＞臀');
  });
  it('GET/PATCH都携带设备头，失败向上抛出保留表单', async () => {
    vi.stubGlobal('localStorage', { getItem: () => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', setItem: () => {} });
    const fetcher = vi.fn(async (_: RequestInfo | URL, options?: RequestInit) => {
      expect(new Headers(options?.headers).get('X-Device-ID')).toBe('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
      return new Response(JSON.stringify({ owner_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', height_cm: 165, weight_kg: null, body_shape: 'H' }), { status: 200 });
    });
    expect((await getProfile(undefined, fetcher)).height_cm).toBe(165);
    await saveProfile({ height_cm: 166, weight_kg: null, body_shape: 'H' }, fetcher);
    expect(fetcher.mock.calls[1][1]?.method).toBe('PATCH');
    expect(JSON.parse(fetcher.mock.calls[1][1]?.body as string).height_cm).toBe(166);
    await expect(saveProfile({ height_cm: 166, weight_kg: null, body_shape: 'H' }, async () => new Response('{"detail":"保存失败，请重试"}', { status: 503 }))).rejects.toThrow('保存失败');
  });
  it('拒绝跨设备响应，旧设备草稿不得提交到新设备', async () => {
    let owner = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    vi.stubGlobal('localStorage', { getItem: () => owner, setItem: () => {} });
    const fetcher = vi.fn(async () => Response.json({ owner_id: owner, height_cm: 165, weight_kg: null, body_shape: 'A' }));
    const loaded = await getProfile(undefined, fetcher);
    owner = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    await expect(saveProfile(loaded, fetcher, loaded.owner_id)).rejects.toThrow('设备');
    expect(fetcher).toHaveBeenCalledTimes(1);
    await expect(getProfile(undefined, async () => Response.json({ owner_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', height_cm: 165, weight_kg: null, body_shape: 'A' }))).rejects.toThrow('归属');
  });
  it('合并组件取消与请求超时信号', async () => {
    vi.stubGlobal('localStorage', { getItem: () => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', setItem: () => {} });
    const controller = new AbortController();
    const fetcher: typeof fetch = async (_, options) => {
      expect(options?.signal).not.toBe(controller.signal);
      return new Promise((_, reject) => options?.signal?.addEventListener('abort', () => reject(new Error('abort')), { once: true }));
    };
    const pending = getProfile(controller.signal, fetcher);
    controller.abort();
    await expect(pending).rejects.toThrow('连接失败');
  });
});
