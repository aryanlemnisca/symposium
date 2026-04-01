import { useState } from 'react';
import { api } from '../../api/client';
import type { SessionData } from '../../store/sessionStore';

interface Props {
  session: SessionData;
  onClose: () => void;
}

export default function SaveTemplateModal({ session, onClose }: Props) {
  const [name, setName] = useState(`${session.name} Template`);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post('/templates', {
        name,
        agents: session.agents,
        settings: session.settings,
        mode: session.mode,
        canvas_state: session.canvas_state,
      });
      onClose();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="w-full max-w-md p-6 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--color-teal)' }}>Save as Template?</h2>
        <p className="text-sm mb-4" style={{ color: 'var(--color-text-dim)' }}>Save this canvas configuration for future sessions.</p>
        <input value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Not now</button>
          <button onClick={handleSave} disabled={saving || !name} className="flex-1 py-2 rounded-lg text-sm font-medium disabled:opacity-50" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{saving ? 'Saving...' : 'Save Template'}</button>
        </div>
      </div>
    </div>
  );
}
