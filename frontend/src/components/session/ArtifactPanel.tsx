import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
}

export default function ArtifactPanel({ messages }: Props) {
  const sections = messages.filter((m) => m.type === 'artifact_section');

  if (sections.length === 0) {
    return (<div className="p-4 text-sm" style={{ color: 'var(--color-text-dim)' }}>Living Artifact will appear here as the session progresses...</div>);
  }

  return (
    <div className="p-4 space-y-4 overflow-y-auto">
      <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>Living Artifact</h3>
      {sections.map((s, i) => (
        <div key={i} className="p-3 rounded-lg text-sm" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
          <p className="text-[10px] mb-2" style={{ color: 'var(--color-text-dim)' }}>Section {s.section_num as number} — {s.section_name as string}</p>
          <p className="whitespace-pre-wrap font-mono text-xs" style={{ color: 'var(--color-text)' }}>{s.content as string}</p>
        </div>
      ))}
    </div>
  );
}
