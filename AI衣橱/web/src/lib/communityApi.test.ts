import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { communityFeed, communityPost, newPostDraft, publishPost, validatePostDraft, watchCommunityPhoto, votePost, addComment } from './communityApi';
const owner = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
beforeEach(() => vi.stubGlobal('localStorage', { getItem: () => owner, setItem() {} }));
afterEach(() => vi.unstubAllGlobals());
const post = { id: 'P1', author: { id: 'U1', nickname: '衣友1' }, kind: 'photo', title: '穿搭', body: '', created_at: new Date().toISOString(), media: [{ id: 'M1', caption: '' }], options: [], likes: 0, comments: 0, votes: 0, liked: false, following: false, my_vote: null, can_delete: true };
const photo = () => new File(['photo'], 'cloth.jpg', { type: 'image/jpeg' });
it('真实信息流带设备头和栏目，空列表合法', async () => {
  const result = await communityFeed('following', null, undefined, async (url, init) => {
    expect(String(url)).toContain('tab=following'); expect(new Headers(init?.headers).get('X-Device-ID')).toBe(owner);
    return Response.json({ posts: [], next_cursor: null });
  }); expect(result.posts).toEqual([]);
});
it('帖子校验字段，不接受缺计数/身份的坏响应', async () => {
  expect(await communityPost('P1', undefined, async () => Response.json(post))).toEqual(post);
  await expect(communityPost('P1', undefined, async () => Response.json({ ...post, likes: -1 }))).rejects.toThrow();
});
it('发布失败保留同一File/草稿ID，重试metadata不变', async () => {
  const draft = { ...newPostDraft('photo'), title: '我的衣物', photos: [photo()] };
  const values: string[] = [];
  const fetcher = vi.fn(async (_: RequestInfo | URL, init?: RequestInit) => { values.push(String((init?.body as FormData).get('metadata'))); return values.length === 1 ? Response.json({ detail: '发布失败，请重试' }, { status: 503 }) : Response.json(post, { status: 201 }); });
  await expect(publishPost(draft, fetcher)).rejects.toThrow('发布失败');
  expect(await publishPost(draft, fetcher)).toEqual(post);expect(values[0]).toBe(values[1]);expect(draft.photos[0].name).toBe('cloth.jpg');
});
it('四种发布校验不硬凑，照片与选项一致', () => {
  expect(() => validatePostDraft(newPostDraft('photo'))).toThrow();
  expect(() => validatePostDraft({ ...newPostDraft('outfit'), title: '搭配', item_ids: ['a','b'] })).not.toThrow();
  expect(() => validatePostDraft({ ...newPostDraft('buy'), title: '买不买', photos: [photo()] })).not.toThrow();
  const poll = { ...newPostDraft('poll'), title: '哪套', options: [{ label: '一' }, { label: '二' }], photos: [photo()] };
  expect(() => validatePostDraft(poll)).toThrow();expect(() => validatePostDraft({ ...poll, photos: [photo(),photo()] })).not.toThrow();
});
it('投票和评论发送原ID，中文冲突可读', async () => {
  await expect(votePost('P1','O1',async (_, init) => { expect(JSON.parse(init?.body as string)).toEqual({ option_id: 'O1' });return Response.json({ detail: '你已投过票' }, { status: 409 }); })).rejects.toThrow('已投过票');
  await addComment('P1','c1','喜欢',async (_, init) => { expect(JSON.parse(init?.body as string)).toEqual({ client_id: 'c1', text: '喜欢' });return Response.json({ id:'r1',author:post.author,text:'喜欢',created_at:post.created_at,can_delete:true }); });
});
it('公开照片ObjectURL在卸载后释放，晚到响应不建URL', async () => {
  const create = vi.spyOn(URL,'createObjectURL');const revoke = vi.spyOn(URL,'revokeObjectURL');const states: string[] = [];
  const resource=watchCommunityPhoto('P1','M1',x=>states.push(x.status),async()=>new Response(new Blob(['jpg'],{type:'image/jpeg'})));
  await vi.waitFor(()=>expect(states).toContain('ready'));resource.dispose();expect(revoke).toHaveBeenCalled();
  let resolve!: (response: Response)=>void;
  const late=watchCommunityPhoto('P1','M1',()=>{},()=>new Promise(r=>resolve=r));late.dispose();const count=create.mock.calls.length;resolve(new Response(new Blob(['jpg'],{type:'image/jpeg'})));await new Promise(r=>setTimeout(r,0));expect(create.mock.calls.length).toBe(count);create.mockRestore();revoke.mockRestore();
});

it('旧设备打开的发布草稿不能在切换设备后提交', async () => {
 const d={...newPostDraft('photo'),title:'草稿',photos:[photo()]};vi.stubGlobal('localStorage',{getItem:()=> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',setItem(){}});
 const noFetch=vi.fn();await expect(publishPost(d,noFetch,undefined,owner)).rejects.toThrow('设备');expect(noFetch).not.toHaveBeenCalled();
});
