import { useEffect, useRef } from 'react';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
}

export default function LiveFeed({ messages }: Props) {
  const feedRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    if (!userScrolledUp.current && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleScroll = () => {
    if (!feedRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = feedRef.current;
    userScrolledUp.current = scrollHeight - scrollTop - clientHeight > 50;
  };

  return (
    <div ref={feedRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-3" style={{ background: 'var(--color-navy)' }}>
      {messages.map((msg, i) => {
        if (msg.type === 'agent_message' && !msg.streaming) {
          return (
            <div key={i} className="p-4 rounded-lg" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>{msg.source as string}</span>
                <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Round {msg.round as number}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)', fontFamily: 'monospace', lineHeight: '1.6' }}>{msg.content as string}</p>
            </div>
          );
        }
        if (msg.type === 'overseer') {
          return (<div key={i} className="p-4 rounded-lg" style={{ background: '#1a1a2e', border: '1px solid #333' }}><p className="text-xs font-mono whitespace-pre-wrap" style={{ color: '#94a3b8' }}>{msg.content as string}</p></div>);
        }
        if (msg.type === 'gate_skip') {
          return (<div key={i} className="px-3 py-1 text-xs" style={{ color: 'var(--color-text-dim)' }}>{msg.agent as string} skipped — no new contribution</div>);
        }
        if (msg.type === 'convergence') {
          return (<div key={i} className="px-3 py-2 text-xs rounded" style={{ background: '#1e1a2e', color: '#a78bfa', border: '1px solid #4c1d95' }}>Convergence detected — forcing {msg.forced_next as string}</div>);
        }
        if (msg.type === 'phase_transition') {
          return (<div key={i} className="py-4 text-center"><div className="inline-block px-4 py-2 rounded-lg text-sm font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{msg.phase === 'prd_panel' ? 'Brainstorm complete. Running PRD panel...' : msg.phase === 'conclusion' ? 'Brainstorm complete. Generating Conclusion Report...' : `Phase: ${msg.phase}`}</div></div>);
        }
        if (msg.type === 'session_complete') {
          return (<div key={i} className="py-4 text-center"><div className="inline-block px-6 py-3 rounded-lg text-sm font-bold" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Session Complete — {msg.terminated_by as string}</div></div>);
        }
        if (msg.type === 'error') {
          return (<div key={i} className="px-3 py-2 text-sm text-red-400 rounded" style={{ background: '#1a0a0a', border: '1px solid #7f1d1d' }}>Error: {msg.message as string}</div>);
        }
        return null;
      })}
    </div>
  );
}
