import type { Phase } from '../../store/sessionStore';

interface Props {
  phases: Phase[];
  onChange: (phases: Phase[]) => void;
  onReinterpret: () => void;
  onConfirm: () => void;
  reinterpreting: boolean;
  confirmed: boolean;
}

export default function PhaseCards({ phases, onChange, onReinterpret, onConfirm, reinterpreting, confirmed }: Props) {
  const updatePhase = (index: number, updates: Partial<Phase>) => {
    const updated = phases.map((p, i) => i === index ? { ...p, ...updates } : p);
    onChange(updated);
  };

  const addSubquestion = (index: number) => {
    const phase = phases[index];
    updatePhase(index, { key_subquestions: [...phase.key_subquestions, ''] });
  };

  const updateSubquestion = (phaseIndex: number, sqIndex: number, value: string) => {
    const phase = phases[phaseIndex];
    const sqs = [...phase.key_subquestions];
    sqs[sqIndex] = value;
    updatePhase(phaseIndex, { key_subquestions: sqs });
  };

  const removeSubquestion = (phaseIndex: number, sqIndex: number) => {
    const phase = phases[phaseIndex];
    updatePhase(phaseIndex, { key_subquestions: phase.key_subquestions.filter((_, i) => i !== sqIndex) });
  };

  const removePhase = (index: number) => {
    const updated = phases.filter((_, i) => i !== index).map((p, i) => ({ ...p, number: i + 1 }));
    onChange(updated);
  };

  if (phases.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>
          Review Phases ({phases.length})
        </h3>
        {!confirmed && (
          <div className="flex gap-2">
            <button onClick={onReinterpret} disabled={reinterpreting} className="text-[10px] px-2 py-1 rounded disabled:opacity-40" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
              {reinterpreting ? 'Re-interpreting...' : 'Re-interpret'}
            </button>
            <button
              onClick={onConfirm}
              disabled={phases.some((p) => !Array.isArray(p.artifact_schema) || p.artifact_schema.length === 0)}
              className="text-[10px] px-2 py-1 rounded font-medium disabled:opacity-40"
              style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
            >
              Confirm Phases
            </button>
          </div>
        )}
      </div>

      {confirmed && (
        <div className="text-[10px] px-3 py-2 rounded-lg" style={{ background: 'rgba(45, 212, 191, 0.1)', border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal)' }}>
          Phases confirmed. Add agents and begin the session.
        </div>
      )}

      {phases.map((phase, i) => (
        <div key={i}>
          {/* Connector */}
          {i > 0 && (
            <div className="flex justify-center py-2">
              <div className="w-0.5 h-6" style={{ background: 'var(--color-border)' }} />
            </div>
          )}

          <div className="p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: `1px solid ${confirmed ? 'var(--color-border)' : 'var(--color-teal-dim)'}` }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{phase.number}</span>
                {confirmed ? (
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{phase.name}</span>
                ) : (
                  <input
                    value={phase.name}
                    onChange={(e) => updatePhase(i, { name: e.target.value })}
                    className="text-sm font-medium bg-transparent outline-none"
                    style={{ color: 'var(--color-text)' }}
                  />
                )}
              </div>
              {!confirmed && (
                <button onClick={() => removePhase(i)} className="text-[10px]" style={{ color: '#f87171' }}>Remove</button>
              )}
            </div>

            <div className="mb-2">
              <label className="text-[10px] block mb-0.5" style={{ color: 'var(--color-text-dim)' }}>Focus Question</label>
              {confirmed ? (
                <p className="text-xs" style={{ color: 'var(--color-text)' }}>{phase.focus_question}</p>
              ) : (
                <textarea
                  value={phase.focus_question}
                  onChange={(e) => updatePhase(i, { focus_question: e.target.value })}
                  rows={2}
                  className="w-full px-2 py-1 rounded text-xs outline-none resize-y"
                  style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              )}
            </div>

            <div className="mb-2">
              <label className="text-[10px] block mb-0.5" style={{ color: 'var(--color-text-dim)' }}>Subquestions</label>
              {phase.key_subquestions.map((sq, sqI) => (
                <div key={sqI} className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] shrink-0" style={{ color: 'var(--color-text-dim)' }}>·</span>
                  {confirmed ? (
                    <span className="text-xs" style={{ color: 'var(--color-text)' }}>{sq}</span>
                  ) : (
                    <>
                      <input
                        value={sq}
                        onChange={(e) => updateSubquestion(i, sqI, e.target.value)}
                        className="flex-1 px-2 py-0.5 rounded text-xs outline-none"
                        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      />
                      <button onClick={() => removeSubquestion(i, sqI)} className="text-[10px] px-1" style={{ color: '#f87171' }}>x</button>
                    </>
                  )}
                </div>
              ))}
              {!confirmed && (
                <button onClick={() => addSubquestion(i)} className="text-[10px] mt-1" style={{ color: 'var(--color-teal-dim)' }}>+ Add subquestion</button>
              )}
            </div>

            <div className="mb-2">
              <label className="text-[10px] block mb-0.5" style={{ color: 'var(--color-teal-dim)' }}>Artifact Sections</label>
              {(!Array.isArray(phase.artifact_schema) || phase.artifact_schema.length === 0) && !confirmed && (
                <div className="p-2 rounded mb-2 text-[10px]" style={{ background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fbbf24' }}>
                  No artifact sections defined. Add sections to specify what this phase's review output should contain.
                </div>
              )}
              {(Array.isArray(phase.artifact_schema) ? phase.artifact_schema : []).map((section, sI) => (
                <div key={sI} className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] shrink-0" style={{ color: 'var(--color-teal-dim)' }}>{sI + 1}.</span>
                  {confirmed ? (
                    <span className="text-xs" style={{ color: 'var(--color-text)' }}>{section}</span>
                  ) : (
                    <>
                      <input
                        value={section}
                        onChange={(e) => {
                          const schema = [...(phase.artifact_schema || [])];
                          schema[sI] = e.target.value;
                          updatePhase(i, { artifact_schema: schema });
                        }}
                        className="flex-1 px-2 py-0.5 rounded text-xs outline-none"
                        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal-dim)', color: 'var(--color-text)' }}
                      />
                      <button onClick={() => {
                        const schema = (phase.artifact_schema || []).filter((_, idx) => idx !== sI);
                        updatePhase(i, { artifact_schema: schema });
                      }} className="text-[10px] px-1" style={{ color: '#f87171' }}>x</button>
                    </>
                  )}
                </div>
              ))}
              {!confirmed && (
                <button onClick={() => {
                  const schema = [...(phase.artifact_schema || []), ''];
                  updatePhase(i, { artifact_schema: schema });
                }} className="text-[10px] mt-1" style={{ color: 'var(--color-teal-dim)' }}>+ Add artifact section</button>
              )}
            </div>

            {phase.rationale && (
              <p className="text-[10px] italic" style={{ color: 'var(--color-text-dim)' }}>{phase.rationale}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
