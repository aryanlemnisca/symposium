import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
  maxRounds: number;
}

export default function StatsBar({ messages, maxRounds }: Props) {
  const latestStats = [...messages].reverse().find((m) => m.type === 'stats');
  const rounds = (latestStats?.rounds as number) || 0;
  const gateSkips = (latestStats?.gate_skips as number) || 0;
  const overseerInjections = messages.filter((m) => m.type === 'overseer').length;

  return (
    <div className="flex items-center gap-6 px-4 py-2 text-xs" style={{ background: 'var(--color-navy-light)', borderBottom: '1px solid var(--color-border)' }}>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Rounds: </span><span style={{ color: 'var(--color-teal)' }}>{rounds} / {maxRounds}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Gate skips: </span><span>{gateSkips}</span></div>
      <div><span style={{ color: 'var(--color-text-dim)' }}>Overseer: </span><span>{overseerInjections}</span></div>
      <div className="flex-1" />
      <div className="w-32 h-1.5 rounded-full" style={{ background: 'var(--color-navy)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${(rounds / maxRounds) * 100}%`, background: 'var(--color-teal)' }} />
      </div>
    </div>
  );
}
