import { useEffect, useRef, useState } from 'react';
import type { WSMessage } from '../../hooks/useWebSocket';

interface AgentInfo {
  name: string;
  tools?: string[];
}

interface Props {
  messages: WSMessage[];
  agents?: AgentInfo[];
}

function CollapsibleMessage({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = content.split('\n');
  const needsCollapse = lines.length > 4;

  return (
    <div>
      <p
        className="text-sm whitespace-pre-wrap"
        style={{
          color: 'var(--color-text)',
          fontFamily: 'monospace',
          lineHeight: '1.6',
          display: '-webkit-box',
          WebkitLineClamp: expanded ? 'unset' : 4,
          WebkitBoxOrient: 'vertical',
          overflow: expanded ? 'visible' : 'hidden',
        }}
      >
        {content}
      </p>
      {needsCollapse && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-1 text-[11px] px-2 py-0.5 rounded"
          style={{ color: 'var(--color-teal-dim)', border: '1px solid var(--color-border)' }}
        >
          {expanded ? 'Show less' : `Show more (${lines.length} lines)`}
        </button>
      )}
    </div>
  );
}

export default function LiveFeed({ messages, agents = [] }: Props) {
  const webSearchAgents = new Set(
    agents.filter((a) => a.tools?.includes('web_search')).map((a) => a.name)
  );
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
        if (msg.type === 'agent_message') {
          const isStreaming = !!msg.streaming;
          const content = (msg.content as string) || '';
          return (
            <div key={i} className="p-4 rounded-lg" style={{ background: 'var(--color-navy-light)', border: `1px solid ${isStreaming ? 'var(--color-teal-dim)' : 'var(--color-border)'}` }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>{msg.source as string}</span>
                {webSearchAgents.has(msg.source as string) && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal)', color: 'var(--color-teal)' }}>W</span>
                )}
                <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Round {msg.round as number}</span>
                {isStreaming && <span className="text-[10px] animate-pulse" style={{ color: 'var(--color-teal-dim)' }}>typing...</span>}
              </div>
              {content ? (
                isStreaming
                  ? <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)', fontFamily: 'monospace', lineHeight: '1.6' }}>{content}</p>
                  : <CollapsibleMessage content={content} />
              ) : (
                isStreaming && <span className="inline-block w-2 h-4 animate-pulse" style={{ background: 'var(--color-teal-dim)' }} />
              )}
            </div>
          );
        }
        if (msg.type === 'overseer') {
          return (<div key={i} className="p-4 rounded-lg" style={{ background: '#1a1a2e', border: '1px solid #333' }}><CollapsibleMessage content={msg.content as string} /></div>);
        }
        if (msg.type === 'gate_skip') {
          return (<div key={i} className="px-3 py-1 text-xs" style={{ color: 'var(--color-text-dim)' }}>{msg.agent as string} skipped — no new contribution</div>);
        }
        if (msg.type === 'convergence') {
          return (<div key={i} className="px-3 py-2 text-xs rounded" style={{ background: '#1e1a2e', color: '#a78bfa', border: '1px solid #4c1d95' }}>Convergence detected — forcing {msg.forced_next as string}</div>);
        }
        if (msg.type === 'phase_transition') {
          const phaseLabels: Record<string, string> = {
            prd_panel: 'Brainstorm complete. Running PRD panel...',
            conclusion: 'Brainstorm complete. Generating Conclusion Report...',
            synthesis: 'PRD panel complete. Generating Synthesis & PRD document...',
          };
          return (<div key={i} className="py-4 text-center"><div className="inline-block px-4 py-2 rounded-lg text-sm font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{phaseLabels[msg.phase as string] || `Phase: ${msg.phase}`}</div></div>);
        }
        if (msg.type === 'phase_directive') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-sm font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                Phase {msg.phase_number as number}: {msg.phase_name as string}
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-dim)' }}>{msg.focus_question as string}</p>
            </div>
          );
        }
        if (msg.type === 'drift_redirect') {
          return (
            <div key={i} className="px-3 py-2 text-xs rounded" style={{ background: '#1a1a2e', border: '1px solid #333', color: '#fbbf24' }}>
              {msg.message as string}
            </div>
          );
        }
        if (msg.type === 'phase_artifact_written') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-xs" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal)' }}>
                Phase {msg.phase_number as number} artifact written
              </div>
            </div>
          );
        }
        if (msg.type === 'verdict_generating') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-sm font-medium animate-pulse" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                Generating final readiness verdict...
              </div>
            </div>
          );
        }
        if (msg.type === 'verdict_complete') {
          return (
            <div key={i} className="py-4">
              <div className="p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal)' }}>
                <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--color-teal)' }}>Final Readiness Verdict</h3>
                <CollapsibleMessage content={msg.content as string} />
              </div>
            </div>
          );
        }
        if (msg.type === 'executive_summary') {
          return (
            <div key={i} className="py-4">
              <div className="p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '2px solid var(--color-teal)' }}>
                <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--color-teal)' }}>Executive Summary</h3>
                <pre className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)', fontFamily: 'monospace', lineHeight: '1.6' }}>{msg.content as string}</pre>
              </div>
            </div>
          );
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
