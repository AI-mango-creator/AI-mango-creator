export const bodyShapes = [
  { id: 'X', name: 'X 型｜沙漏型', description: '肩≈臀宽、腰明显收窄，曲线感强', outline: 'M27 24 L10 32 L18 49 L32 61 L18 82 L15 108 L65 108 L62 82 L48 61 L62 49 L70 32 L53 24 Z' },
  { id: 'A', name: 'A 型｜梨型', description: '肩窄、腰细，臀 & 大腿更宽，下半身丰满', outline: 'M29 24 L23 32 L26 48 L31 60 L17 80 L9 108 L71 108 L63 80 L49 60 L54 48 L57 32 L51 24 Z' },
  { id: 'TY', name: 'T/Y 型｜倒三角', description: '肩宽、上半身壮，臀窄，肩＞臀', outline: 'M27 24 L4 32 L15 50 L29 64 L27 85 L25 108 L55 108 L53 85 L51 64 L65 50 L76 32 L53 24 Z' },
  { id: 'H', name: 'H 型｜直筒 / 香蕉型', description: '肩、腰、臀宽度接近，腰线不突出', outline: 'M27 24 L18 32 L20 54 L22 72 L18 94 L17 108 L63 108 L62 94 L58 72 L60 54 L62 32 L53 24 Z' },
  { id: 'O', name: 'O 型｜苹果型', description: '腰腹脂肪多、肚子突出，四肢偏细', outline: 'M28 24 Q17 27 14 41 Q4 64 12 83 L25 91 L26 108 L54 108 L55 91 Q76 83 72 61 Q68 35 52 24 Z' },
] as const;

export type BodyShape = typeof bodyShapes[number]['id'];

export default function BodyShapeGuide({ value, onChange, disabled = false }: {
  value: BodyShape | ''; onChange: (shape: BodyShape | '') => void; disabled?: boolean;
}) {
  return <fieldset disabled={disabled} className="min-w-0">
    <legend className="mb-3 font-semibold">体型画像（五选一）</legend>
    <p className="mb-3 text-xs leading-5 text-slate-500">示意图用于帮助选择，按肩、腰、臀的相对比例判断。</p>
    <div className="grid min-w-0 grid-cols-1 gap-3">
      {bodyShapes.map(shape => <label key={shape.id} className={`flex min-w-0 cursor-pointer items-center gap-3 rounded-xl border p-3 ${value === shape.id ? 'border-sky-600 bg-sky-50' : 'border-slate-200 bg-white'}`}>
        <input type="radio" name="body-shape" value={shape.id} checked={value === shape.id} onChange={() => onChange(shape.id)} className="shrink-0" />
        <svg viewBox="0 0 80 118" role="img" aria-label={`${shape.name}体型示意图`} className="h-28 w-16 shrink-0">
          <circle cx="40" cy="12" r="10" fill="#b3d5df" />
          <path d={shape.outline} fill="#b3d5df" stroke="#477a8c" strokeWidth="1.5" />
          <path d="M8 36 H72 M8 64 H72 M8 88 H72" stroke="#477a8c" strokeWidth="1" strokeDasharray="3 3" opacity=".55" />
        </svg>
        <span className="min-w-0"><span className="block text-sm font-semibold">{shape.name}</span><span className="mt-2 block text-xs leading-5 text-slate-600">{shape.description}</span></span>
      </label>)}
    </div>
    <button type="button" className="mt-3 text-sm text-sky-800 underline" onClick={() => onChange('')}>清除体型选择</button>
  </fieldset>;
}
