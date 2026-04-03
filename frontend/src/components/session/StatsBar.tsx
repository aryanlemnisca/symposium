import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
  maxRounds: number;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export default function StatsBar({ messages, maxRounds }: Props) {
  const latestStats = [...messages].reverse().find((m) => m.type === 'stats');
  const rounds = (latestStats?.rounds as number) || 0;
  const gateSkips = (latestStats?.gate_skips as number) || 0;
  const overseerInjections = messages.filter((m) => m.type === 'overseer').length;
  const elapsed = (latestStats?.elapsed_seconds as number) || 0;
  const eta = (latestStats?.eta_seconds as number) || 0;

  return (
    <div className="flex items-center gap-6 px-4 py-2 text-xs" style={{ background: 'var(--color-navy-light)', borderBottom: '1px solid var(--color-border)' }}>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Rounds: </span><span style={{ color: 'var(--color-teal)' }}>{rounds} / {maxRounds}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Gate skips: </span><span>{gateSkips}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Overseer: </span><span>{overseerInjections}</span></div>
      {elapsed > 0 && (
        <div><span style={{ color: 'var(--color-text-dim)' }}>Elapsed: </span><span>{formatTime(elapsed)}</span></div>
      )}
      {eta > 0 && rounds >= 3 && (
        <div><span style={{ color: 'var(--color-text-dim)' }}>ETA: </span><span style={{ color: '#fbbf24' }}>~{formatTime(eta)}</span></div>
      )}
      <div className="flex-1" />
      <div className="w-32 h-1.5 rounded-full" style={{ background: 'var(--color-navy)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${(rounds / maxRounds) * 100}%`, background: 'var(--color-teal)' }} />
      </div>
    </div>
  );
}
