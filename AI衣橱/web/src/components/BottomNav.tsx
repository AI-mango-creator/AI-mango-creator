import AppIcon from './AppIcon';
export type Page = 'my' | 'home' | 'wardrobe' | 'outfits' | 'profile' | 'weather' | 'community';
const links = [{ page: 'home', label: '首页', icon: 'home' }, { page: 'wardrobe', label: '衣橱', icon: 'wardrobe' }, { page: 'community', label: '社区', icon: 'community' }, { page: 'my', label: '我的', icon: 'person' }] as const;
export default function BottomNav({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }) {
  return <nav aria-label="页面切换" className="bottom-nav">{links.map(link => <button key={link.page} type="button" aria-current={(page === link.page || page === 'profile' && link.page === 'my' || page === 'outfits' && link.page === 'wardrobe') ? 'page' : undefined} onClick={() => onNavigate(link.page)}><AppIcon name={link.icon} /><span>{link.label}</span></button>)}</nav>;
}
