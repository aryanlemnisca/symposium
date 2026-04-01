import { useCanvasStore } from '../../store/canvasStore';

const MODELS = [
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Quality)' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)' },
];

export default function AgentDrawer() {
  const { nodes, selectedNodeId, drawerOpen, setDrawerOpen, updateAgent, removeAgent } = useCanvasStore();

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!drawerOpen || !node) return null;

  const data = node.data;

  const update = (field: string, value: unknown) => {
    updateAgent(node.id, { [field]: value });
  };

  return (
    <div
      className="fixed right-0 top-0 h-full w-96 overflow-y-auto z-50 p-6"
      style={{
        background: 'var(--color-navy-light)',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>Agent Config</h2>
        <button onClick={() => setDrawerOpen(false)} className="text-sm px-2 py-1" style={{ color: 'var(--color-text-dim)' }}>Close</button>
      </div>

      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Name</label>
      <input value={data.name || ''} onChange={(e) => update('name', e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />

      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Model</label>
      <select value={data.model || MODELS[0].value} onChange={(e) => update('model', e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>
        {MODELS.map((m) => (<option key={m.value} value={m.value}>{m.label}</option>))}
      </select>

      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Role Tag</label>
      <input value={data.role_tag || ''} onChange={(e) => update('role_tag', e.target.value)} placeholder="e.g. Challenger, Domain Expert" className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />

      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Persona Definition</label>
      <textarea value={data.persona || ''} onChange={(e) => update('persona', e.target.value)} rows={12} placeholder="Define this agent's background, worldview, what they care about..." className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none resize-y" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)', fontFamily: 'monospace' }} />

      <div className="flex items-center justify-between mb-6">
        <span className="text-sm" style={{ color: 'var(--color-text)' }}>Web Search</span>
        <button onClick={() => { const tools = data.tools || []; update('tools', tools.includes('web_search') ? tools.filter((t: string) => t !== 'web_search') : [...tools, 'web_search']); }} className="px-3 py-1 rounded-full text-xs" style={{ background: (data.tools || []).includes('web_search') ? 'var(--color-teal)' : 'var(--color-navy)', color: (data.tools || []).includes('web_search') ? 'var(--color-navy)' : 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}>
          {(data.tools || []).includes('web_search') ? 'ON' : 'OFF'}
        </button>
      </div>

      <button onClick={() => { removeAgent(node.id); setDrawerOpen(false); }} className="w-full py-2 rounded-lg text-sm text-red-400 hover:bg-red-900/20 transition-colors" style={{ border: '1px solid rgba(248, 113, 113, 0.3)' }}>Remove Agent</button>
    </div>
  );
}
