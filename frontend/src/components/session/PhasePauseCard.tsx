import { useState, useEffect } from 'react';

interface Props {
  phaseNumber: number;
  summary: string;
  confirmed: string[];
  contested: string[];
  openQuestions: string[];
  hasNextPhase: boolean;
  onAdvance: () => void;
  onContinue: () => void;
  onPauseTimer: () => void;
}

export default function PhasePauseCard({ phaseNumber, summary, confirmed, contested, openQuestions, hasNextPhase, onAdvance, onContinue, onPauseTimer }: Props) {
  const [countdown, setCountdown] = useState(60);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    if (countdown <= 0) {
      onAdvance();
      return;
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown, paused, onAdvance]);

  const handlePause = () => {
    setPaused(true);
    onPauseTimer();
  };

  return (
    <div className="my-4 p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal)' }}>
      <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--color-teal)' }}>
        Phase {phaseNumber} Review Complete
      </h3>

      {summary && <p className="text-xs mb-3" style={{ color: 'var(--color-text)' }}>{summary}</p>}

      {confirmed.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] font-medium" style={{ color: '#2dd4bf' }}>Confirmed:</p>
          <ul className="pl-3">{confirmed.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      {contested.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] font-medium" style={{ color: '#fbbf24' }}>Contested:</p>
          <ul className="pl-3">{contested.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      {openQuestions.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] font-medium" style={{ color: '#f87171' }}>Open Questions:</p>
          <ul className="pl-3">{openQuestions.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      <div className="flex items-center gap-2">
        {hasNextPhase ? (
          <button onClick={onAdvance} className="flex-1 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
            Advance to Phase {phaseNumber + 1}
          </button>
        ) : (
          <button onClick={onAdvance} className="flex-1 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
            Generate Final Verdict
          </button>
        )}
        <button onClick={onContinue} className="flex-1 py-2 rounded-lg text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
          Continue Phase {phaseNumber}
        </button>
      </div>

      <div className="flex items-center justify-between mt-2">
        {!paused ? (
          <>
            <span className="text-[10px]" style={{ color: countdown <= 10 ? '#f87171' : 'var(--color-text-dim)' }}>
              Auto-advancing in {countdown}s
            </span>
            <button onClick={handlePause} className="text-[10px] px-2 py-0.5 rounded" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
              Pause Timer
            </button>
          </>
        ) : (
          <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>Timer paused — waiting for your decision</span>
        )}
      </div>
    </div>
  );
}
