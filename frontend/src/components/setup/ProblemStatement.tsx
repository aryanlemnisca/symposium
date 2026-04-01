import { useInlineSuggestion, useReview } from '../../hooks/useAISuggest';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ProblemStatement({ value, onChange }: Props) {
  const { suggestion, dismiss } = useInlineSuggestion(value);
  const { review, loading: reviewing, result: reviewResult, clearResult } = useReview();

  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>Problem Statement</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={6} placeholder="Describe the problem, goal, or question this session should address..." className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />

      <div className="flex justify-between items-center mt-1">
        <span className="text-[10px]" style={{ color: value.length < 100 ? '#f87171' : 'var(--color-text-dim)' }}>{value.length} chars</span>
        <button onClick={() => review(value, 'problem_statement')} disabled={reviewing || value.length < 20} className="text-[10px] px-2 py-1 rounded disabled:opacity-40" style={{ border: '1px solid var(--color-border)', color: 'var(--color-teal-dim)' }}>{reviewing ? 'Reviewing...' : 'Review'}</button>
      </div>

      {suggestion && (
        <div className="mt-2 p-2 rounded-lg flex items-center justify-between text-xs" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal-dim)' }}>
          <span style={{ color: 'var(--color-text-dim)' }}>{suggestion}</span>
          <button onClick={dismiss} className="ml-2 text-[10px]" style={{ color: 'var(--color-text-dim)' }}>dismiss</button>
        </div>
      )}

      {reviewResult && (
        <div className="mt-3 p-3 rounded-lg text-xs space-y-2" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
          <div className="flex justify-between">
            <span style={{ color: 'var(--color-text-dim)' }}>Clarity: <strong style={{ color: (reviewResult.clarity as string) === 'High' ? '#2dd4bf' : (reviewResult.clarity as string) === 'Medium' ? '#fbbf24' : '#f87171' }}>{reviewResult.clarity as string}</strong></span>
            <button onClick={clearResult} className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>close</button>
          </div>
          {(reviewResult.missing as string[])?.length > 0 && (
            <div>
              <p style={{ color: '#f87171' }}>Missing:</p>
              <ul className="pl-3">{(reviewResult.missing as string[]).map((m, i) => <li key={i} style={{ color: 'var(--color-text-dim)' }}>- {m}</li>)}</ul>
            </div>
          )}
          {(reviewResult.suggestions as string[])?.length > 0 && (
            <div>
              <p style={{ color: 'var(--color-teal-dim)' }}>Suggestions:</p>
              <ul className="pl-3">{(reviewResult.suggestions as string[]).map((s, i) => <li key={i} style={{ color: 'var(--color-text-dim)' }}>- {s}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
