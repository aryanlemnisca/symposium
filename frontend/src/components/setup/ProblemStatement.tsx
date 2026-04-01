interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ProblemStatement({ value, onChange }: Props) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>Problem Statement</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={6} placeholder="Describe the problem, goal, or question this session should address..." className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
      <div className="flex justify-between mt-1">
        <span className="text-[10px]" style={{ color: value.length < 100 ? '#f87171' : 'var(--color-text-dim)' }}>{value.length} chars {value.length < 100 ? '(100+ recommended)' : ''}</span>
      </div>
    </div>
  );
}
