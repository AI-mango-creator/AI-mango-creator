export type IconName = 'home' | 'wardrobe' | 'spark' | 'person' | 'sun' | 'cloud' | 'rain' | 'upload' | 'arrow' | 'back' | 'edit';
const paths: Record<IconName, string> = {
  home: 'M3 10 12 2l9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  wardrobe: 'M4 3h16v17H4z M12 3v17 M8 9v5 M16 9v5 M6 20v2 M18 20v2',
  spark: 'm12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z',
  person: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M4 22v-3a8 5 0 0 1 16 0v3Z',
  sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z M12 1v2 M12 21v2 M1 12h2 M21 12h2 M4 4l2 2 M18 18l2 2 M4 20l2-2 M18 6l2-2',
  cloud: 'M6 18a4 4 0 1 1 0-8 6 6 0 0 1 12-1 4.5 4.5 0 0 1 0 9Z',
  rain: 'M6 15a4 4 0 1 1 0-8 6 6 0 0 1 12-1 4.5 4.5 0 0 1 0 9Z M7 18l-1 4 M13 18l-1 4 M19 18l-1 4',
  upload: 'M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6',
  arrow: 'm9 4 8 8-8 8', back: 'm15 4-8 8 8 8',
  edit: 'm4 16 12-12 4 4L8 20H4Z M14 6l4 4',
};
export function weatherIcon(code: number): IconName { return code <= 1 ? 'sun' : code >= 51 ? 'rain' : 'cloud'; }
export default function AppIcon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg aria-hidden="true" className={`app-icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>;
}
