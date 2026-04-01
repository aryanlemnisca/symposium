interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ModeSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-navy)' }}>
      {[
        { key: 'product', label: 'Product Discussion' },
        { key: 'problem_discussion', label: 'Problem Discussion' },
      ].map((mode) => (
        <button key={mode.key} onClick={() => onChange(mode.key)} className="flex-1 py-2 rounded-md text-xs font-medium transition-colors" style={{ background: value === mode.key ? 'var(--color-teal)' : 'transparent', color: value === mode.key ? 'var(--color-navy)' : 'var(--color-text-dim)' }}>
          {mode.label}
        </button>
      ))}
    </div>
  );
}
