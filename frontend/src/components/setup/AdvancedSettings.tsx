import { useState } from 'react';

interface SessionSettings {
  max_rounds: number;
  temperature: number;
  gate_start_round: number;
  overseer_interval: number;
  min_rounds_before_convergence: number;
  prd_panel_rounds: number;
}

interface Props {
  settings: SessionSettings;
  onChange: (settings: SessionSettings) => void;
}

const ROUND_OPTIONS = [
  { value: 20, cost: '~$0.51' },
  { value: 50, cost: '~$1.27' },
  { value: 80, cost: '~$2.40' },
  { value: 100, cost: '~$3.80' },
];

export default function AdvancedSettings({ settings, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);

  const update = (key: keyof SessionSettings, value: number) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div>
      <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-dim)' }}>Rounds</label>
      <div className="flex gap-2 mb-4">
        {ROUND_OPTIONS.map((opt) => (
          <button key={opt.value} onClick={() => update('max_rounds', opt.value)} className="flex-1 py-2 rounded-lg text-center" style={{ background: settings.max_rounds === opt.value ? 'var(--color-teal)' : 'var(--color-navy)', color: settings.max_rounds === opt.value ? 'var(--color-navy)' : 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}>
            <div className="text-sm font-bold">{opt.value}</div>
            <div className="text-[10px]">{opt.cost}</div>
          </button>
        ))}
      </div>

      <button onClick={() => setExpanded(!expanded)} className="text-xs mb-3" style={{ color: 'var(--color-text-dim)' }}>{expanded ? '- Hide' : '+ Show'} Advanced Settings</button>

      {expanded && (
        <div className="space-y-3">
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Gate Start Round</label>
            <input type="number" value={settings.gate_start_round} onChange={(e) => update('gate_start_round', parseInt(e.target.value))} className="w-full px-2 py-1 rounded text-sm" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Overseer Interval</label>
            <input type="number" value={settings.overseer_interval} onChange={(e) => update('overseer_interval', parseInt(e.target.value))} className="w-full px-2 py-1 rounded text-sm" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Temperature ({settings.temperature})</label>
            <input type="range" min="0.3" max="1.0" step="0.05" value={settings.temperature} onChange={(e) => update('temperature', parseFloat(e.target.value))} className="w-full" />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Min Rounds Before Consensus</label>
            <input type="number" value={settings.min_rounds_before_convergence} onChange={(e) => update('min_rounds_before_convergence', parseInt(e.target.value))} className="w-full px-2 py-1 rounded text-sm" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }} />
          </div>
        </div>
      )}
    </div>
  );
}
