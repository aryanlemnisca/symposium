import { useState, useEffect, useRef } from 'react';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
  maxRounds: number;
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (h > 0) return `${pad(h)}:${pad(m)}:${pad(s)}`;
  return `${pad(m)}:${pad(s)}`;
}

export default function StatsBar({ messages, maxRounds }: Props) {
  const latestStats = [...messages].reverse().find((m) => m.type === 'stats');
  const rounds = (latestStats?.rounds as number) || 0;
  const gateSkips = (latestStats?.gate_skips as number) || 0;
  const overseerInjections = messages.filter((m) => m.type === 'overseer').length;
  const eta = (latestStats?.eta_seconds as number) || 0;
  const phaseNumber = (latestStats?.phase_number as number) || null;
  const phaseName = (latestStats?.phase_name as string) || '';
  const subPhase = (latestStats?.sub_phase as string) || '';
  const totalPhases = (latestStats?.total_phases as number) || 0;

  // Live ticking clock
  const startRef = useRef<number>(Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-6 px-4 py-2 text-xs flex-1" style={{ background: 'var(--color-navy-light)' }}>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Rounds: </span><span style={{ color: 'var(--color-teal)' }}>{rounds} / {maxRounds}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Gate skips: </span><span>{gateSkips}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Overseer: </span><span>{overseerInjections}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>{formatTime(elapsed)}</span></div>
      {eta > 0 && rounds >= 3 && (
        <div><span style={{ color: 'var(--color-text-dim)' }}>ETA: </span><span style={{ color: '#fbbf24' }}>~{formatTime(eta)}</span></div>
      )}
      {phaseNumber && (
        <div><span style={{ color: 'var(--color-text-dim)' }}>Phase: </span><span style={{ color: 'var(--color-teal)' }}>{phaseNumber}/{totalPhases}</span><span style={{ color: 'var(--color-text-dim)' }}> — {phaseName}</span></div>
      )}
      {subPhase && (
        <div><span style={{ color: 'var(--color-text-dim)' }}>{subPhase}</span></div>
      )}
      <div className="flex-1" />
      <div className="w-32 h-1.5 rounded-full" style={{ background: 'var(--color-navy)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${(rounds / maxRounds) * 100}%`, background: 'var(--color-teal)' }} />
      </div>
    </div>
  );
}
