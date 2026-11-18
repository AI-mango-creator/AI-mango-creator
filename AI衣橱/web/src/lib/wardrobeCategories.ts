export const wardrobeGroups = {
  all: '全部', tops: '上装', bottoms: '下装', skirts: '裙装', sets: '套装', shoes: '鞋子',
  bags: '包包', jewelry: '首饰', accessories: '配饰', unclassified: '未分类',
} as const;
export type GroupFilter = keyof typeof wardrobeGroups;
export type WardrobeGroup = Exclude<GroupFilter, 'all'>;
type Classifiable = { category?: string | null; sub?: string | null; wardrobe_group?: string | null };

export function groupOf(item: Classifiable): WardrobeGroup {
  if (item.wardrobe_group) return item.wardrobe_group !== 'all' && Object.hasOwn(wardrobeGroups, item.wardrobe_group)
    ? item.wardrobe_group as WardrobeGroup : 'unclassified';
  if (item.category === 'bottom' && item.sub?.includes('裙')) return 'skirts';
  return ({ top: 'tops', outer: 'tops', bottom: 'bottoms', dress: 'skirts', shoes: 'shoes', accessory: 'accessories' } as Record<string, WardrobeGroup>)[item.category ?? ''] ?? 'unclassified';
}

export function filterGroup<T extends Classifiable>(items: T[], group: GroupFilter): T[] {
  return group === 'all' ? items : items.filter(item => groupOf(item) === group);
}

export function countGroups(items: Classifiable[]): Record<GroupFilter, number> {
  const counts = Object.fromEntries(Object.keys(wardrobeGroups).map(key => [key, 0])) as Record<GroupFilter, number>;
  counts.all = items.length;
  for (const item of items) counts[groupOf(item)]++;
  return counts;
}

export function classificationPatch(group: string, sub: string): { wardrobe_group: WardrobeGroup; sub: string } {
  if (group === 'all' || group === 'unclassified' || !Object.hasOwn(wardrobeGroups, group)) throw new Error('请选择明确的衣橱分类。');
  if (!sub.trim()) throw new Error('请填写具体品类名称，例如衬衫或项链。');
  return { wardrobe_group: group as WardrobeGroup, sub: sub.trim() };
}
