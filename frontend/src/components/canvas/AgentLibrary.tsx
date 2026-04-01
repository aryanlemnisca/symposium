import { useState, useEffect } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { api } from '../../api/client';

interface TemplateAgent {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  canvas_position: { x: number; y: number };
}

interface Template {
  id: string;
  name: string;
  agents: TemplateAgent[];
  is_default: boolean;
}

export default function AgentLibrary() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [search, setSearch] = useState('');
  const addAgent = useCanvasStore((s) => s.addAgent);
  const nodes = useCanvasStore((s) => s.nodes);

  useEffect(() => {
    api.get<Template[]>('/templates').then(setTemplates).catch(() => {});
  }, []);

  const defaultTemplate = templates.find((t) => t.is_default);
  const libraryAgents = defaultTemplate?.agents || [];

  const filteredAgents = libraryAgents.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    (a.role_tag || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleAddBlank = () => {
    const offset = nodes.length * 30;
    addAgent(
      { id: '', name: 'New_Agent', model: 'gemini-3.1-pro-preview', persona: '', tools: [], role_tag: null },
      { x: 250 + offset, y: 250 + offset },
    );
  };

  const handleAddLibraryAgent = (agent: TemplateAgent) => {
    const offset = nodes.length * 30;
    addAgent(
      { id: '', name: agent.name, model: agent.model, persona: agent.persona, tools: agent.tools, role_tag: agent.role_tag },
      { x: agent.canvas_position?.x || (250 + offset), y: agent.canvas_position?.y || (250 + offset) },
    );
  };

  return (
    <div className="w-64 h-full overflow-y-auto p-4 flex flex-col gap-3" style={{ background: 'var(--color-navy-light)', borderLeft: '1px solid var(--color-border)' }}>
      <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>Agents</h3>

      <button onClick={handleAddBlank} className="w-full py-3 rounded-lg text-sm font-medium transition-colors" style={{ background: 'var(--color-navy)', border: '2px dashed var(--color-border)', color: 'var(--color-text-dim)' }}>+ Blank Agent</button>

      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search agents..." className="w-full px-3 py-2 rounded-lg text-xs outline-none" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />

      {defaultTemplate && (
        <div>
          <p className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-dim)' }}>{defaultTemplate.name}</p>
          {filteredAgents.map((agent) => (
            <button key={agent.id || agent.name} onClick={() => handleAddLibraryAgent(agent)} className="w-full text-left p-3 rounded-lg mb-2 hover:opacity-80 transition-opacity" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{agent.name.replace(/_/g, ' ')}</p>
              {agent.role_tag && (<span className="text-[10px]" style={{ color: 'var(--color-teal-dim)' }}>{agent.role_tag}</span>)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
