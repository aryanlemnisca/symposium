import { useState } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { api } from '../../api/client';

const MODELS = [
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Quality)' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)' },
];

export default function AgentDrawer() {
  const { nodes, selectedNodeId, drawerOpen, setDrawerOpen, updateAgent, removeAgent } = useCanvasStore();
  const [reviewing, setReviewing] = useState(false);
  const [reviewResult, setReviewResult] = useState<Record<string, unknown> | null>(null);
  const [enhancedPersona, setEnhancedPersona] = useState<string | null>(null);

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!drawerOpen || !node) return null;

  const data = node.data;

  const update = (field: string, value: unknown) => {
    updateAgent(node.id, { [field]: value });
    setReviewResult(null);
    setEnhancedPersona(null);
  };

  const handleReviewPersona = async () => {
    if (!data.persona) return;
    setReviewing(true);
    setReviewResult(null);
    setEnhancedPersona(null);
    try {
      const otherAgents = nodes
        .filter((n) => n.id !== node.id)
        .map((n) => ({ name: n.data.name, persona: n.data.persona, role_tag: n.data.role_tag }));
      const res = await api.post<{ result: Record<string, unknown> }>('/suggest/review', {
        text: data.persona,
        review_type: 'persona',
        other_agents: [{ name: data.name }, ...otherAgents],
      });
      setReviewResult(res.result);
    } catch {
      // ignore
    } finally {
      setReviewing(false);
    }
  };

  const handleEnhancePersona = async () => {
    if (!data.persona) return;
    setReviewing(true);
    try {
      const otherAgents = nodes
        .filter((n) => n.id !== node.id)
        .map((n) => ({ name: n.data.name, persona: n.data.persona, role_tag: n.data.role_tag }));
      const res = await api.post<{ result: string }>('/suggest/enhance-persona', {
        name: data.name,
        persona: data.persona,
        role_tag: data.role_tag,
        other_agents: otherAgents,
      });
      if (res.result && res.result !== data.persona) {
        setEnhancedPersona(res.result);
      }
    } catch {
      // ignore
    } finally {
      setReviewing(false);
    }
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

      <div className="flex gap-2 mb-4">
        <button onClick={handleReviewPersona} disabled={reviewing || !data.persona} className="flex-1 py-1.5 rounded text-[11px] disabled:opacity-40" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
          {reviewing ? 'Analyzing...' : 'Review'}
        </button>
        <button onClick={handleEnhancePersona} disabled={reviewing || !data.persona} className="flex-1 py-1.5 rounded text-[11px] disabled:opacity-40" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>
          Enhance
        </button>
      </div>

      {/* Enhanced persona preview */}
      {enhancedPersona && (
        <div className="mb-4 p-3 rounded-lg text-xs space-y-2" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal)' }}>
          <div className="flex justify-between items-center">
            <span className="font-medium" style={{ color: 'var(--color-teal)' }}>Enhanced Persona</span>
            <button onClick={() => setEnhancedPersona(null)} className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>dismiss</button>
          </div>
          <p className="whitespace-pre-wrap" style={{ color: 'var(--color-text)', lineHeight: '1.5', fontFamily: 'monospace' }}>{enhancedPersona}</p>
          <div className="flex gap-2 pt-1">
            <button onClick={() => { update('persona', enhancedPersona); setEnhancedPersona(null); }} className="flex-1 py-1.5 rounded text-[11px] font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Accept</button>
            <button onClick={() => setEnhancedPersona(null)} className="flex-1 py-1.5 rounded text-[11px]" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Keep Original</button>
          </div>
        </div>
      )}

      {/* Review results */}
      {reviewResult && (
        <div className="mb-4 p-3 rounded-lg text-xs space-y-2" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
          <div className="flex justify-between">
            <span style={{ color: 'var(--color-text-dim)' }}>Distinctiveness: <strong style={{ color: (reviewResult.distinctiveness as string) === 'High' ? '#2dd4bf' : (reviewResult.distinctiveness as string) === 'Medium' ? '#fbbf24' : '#f87171' }}>{reviewResult.distinctiveness as string}</strong></span>
            <button onClick={() => setReviewResult(null)} className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>close</button>
          </div>
          {reviewResult.distinctiveness_reason && (
            <p style={{ color: 'var(--color-text-dim)' }}>{String(reviewResult.distinctiveness_reason)}</p>
          )}
          {(reviewResult.missing_sections as string[])?.length > 0 && (
            <div>
              <p style={{ color: '#f87171' }}>Missing:</p>
              <ul className="pl-3">{(reviewResult.missing_sections as string[]).map((m, i) => <li key={i} style={{ color: 'var(--color-text-dim)' }}>- {m}</li>)}</ul>
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

      <div className="flex items-center justify-between mb-6">
        <span className="text-sm" style={{ color: 'var(--color-text)' }}>Web Search</span>
        <button onClick={() => { const tools = data.tools || []; updateAgent(node.id, { tools: tools.includes('web_search') ? tools.filter((t: string) => t !== 'web_search') : [...tools, 'web_search'] }); }} className="px-3 py-1 rounded-full text-xs" style={{ background: (data.tools || []).includes('web_search') ? 'var(--color-teal)' : 'var(--color-navy)', color: (data.tools || []).includes('web_search') ? 'var(--color-navy)' : 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}>
          {(data.tools || []).includes('web_search') ? 'ON' : 'OFF'}
        </button>
      </div>

      <button onClick={() => { removeAgent(node.id); setDrawerOpen(false); }} className="w-full py-2 rounded-lg text-sm text-red-400 hover:bg-red-900/20 transition-colors" style={{ border: '1px solid rgba(248, 113, 113, 0.3)' }}>Remove Agent</button>
    </div>
  );
}
