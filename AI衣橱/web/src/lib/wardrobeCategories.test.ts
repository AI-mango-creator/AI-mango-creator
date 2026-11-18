import { describe, expect, it } from 'vitest';
import { classificationPatch, countGroups, filterGroup, groupOf, wardrobeGroups } from './wardrobeCategories';

describe('衣橱分类', () => {
  it('显示全部及九个既定分类，外套归上装，半裙和连衣裙归裙装', () => {
    expect(Object.values(wardrobeGroups)).toEqual(['全部', '上装', '下装', '裙装', '套装', '鞋子', '包包', '首饰', '配饰', '未分类']);
    expect(groupOf({ category: 'outer', sub: '风衣' })).toBe('tops');
    expect(groupOf({ category: 'dress', sub: '连衣裙' })).toBe('skirts');
    expect(groupOf({ category: 'bottom', sub: '半身裙' })).toBe('skirts');
  });
  it('未知归未分类，分类计数与筛选准确', () => {
    const items = [{ category: 'top', sub: '衬衫' }, { wardrobe_group: 'bags', category: null }, { category: null }];
    expect(groupOf(items[2])).toBe('unclassified');
    expect(countGroups(items)).toMatchObject({ all: 3, tops: 1, bags: 1, unclassified: 1, jewelry: 0 });
    expect(filterGroup(items, 'bags')).toEqual([items[1]]);
    expect(filterGroup(items, 'jewelry')).toEqual([]);
  });
  it('手工分类必须选既定分类并填具体名称，去掉首尾空白', () => {
    expect(classificationPatch('jewelry', ' 项链 ')).toEqual({ wardrobe_group: 'jewelry', sub: '项链' });
    for (const group of ['all', 'unclassified', 'new-category', '']) expect(() => classificationPatch(group, '项链')).toThrow();
    expect(() => classificationPatch('jewelry', ' ')).toThrow();
  });
});
