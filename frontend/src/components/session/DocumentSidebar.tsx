import type { UploadedDocument, Phase } from '../../store/sessionStore';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  documents: UploadedDocument[];
  phases: Phase[];
  currentPhaseIndex: number;
  messages?: WSMessage[];
}

export default function DocumentSidebar({ documents, phases, currentPhaseIndex, messages = [] }: Props) {
  const currentPhase = phases[currentPhaseIndex];
  const currentDocIds = new Set(currentPhase?.document_ids || []);
  const previousDocIds = new Set(
    phases.slice(0, currentPhaseIndex).flatMap((p) => p.document_ids || [])
  );

  // Extract live stats
  const latestStats = [...messages].reverse().find((m) => m.type === 'stats');
  const subPhase = (latestStats?.sub_phase as string) || '';
  const phaseRound = (latestStats?.phase_round as number) || 0;

  // Count completed phases
  const completedPhases = phases.filter((p) => p.status === 'complete').length;

  const getDocStatus = (docId: string): 'current' | 'previous' | 'future' => {
    if (currentDocIds.has(docId)) return 'current';
    if (previousDocIds.has(docId)) return 'previous';
    return 'future';
  };

  const statusStyles = {
    current: { border: '1px solid var(--color-teal)', color: 'var(--color-text)', opacity: 1 },
    previous: { border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', opacity: 0.6 },
    future: { border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', opacity: 0.3 },
  };

  const statusLabels = { current: 'Active', previous: 'Reviewed', future: 'Upcoming' };

  return (
    <div className="h-full overflow-y-auto p-3 flex flex-col gap-3" style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}>

      {/* Phase progress */}
      <div>
        <h3 className="text-xs font-bold mb-2" style={{ color: 'var(--color-teal)' }}>Review Progress</h3>
        <div className="space-y-1.5">
          {phases.map((phase, i) => {
            const isActive = i === currentPhaseIndex;
            const isComplete = phase.status === 'complete' || i < currentPhaseIndex;
            return (
              <div key={i} className="flex items-center gap-2 text-[10px]">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold ${isActive ? 'animate-pulse' : ''}`}
                  style={{
                    background: isComplete ? 'var(--color-teal)' : isActive ? 'var(--color-teal-dim)' : 'var(--color-navy)',
                    color: isComplete || isActive ? 'var(--color-navy)' : 'var(--color-text-dim)',
                    border: `1px solid ${isComplete ? 'var(--color-teal)' : isActive ? 'var(--color-teal)' : 'var(--color-border)'}`,
                  }}
                >
                  {isComplete ? '✓' : phase.number}
                </div>
                <span style={{ color: isActive ? 'var(--color-text)' : 'var(--color-text-dim)', fontWeight: isActive ? 600 : 400 }}>
                  {phase.name}
                </span>
              </div>
            );
          })}
        </div>
        <div className="mt-2 text-[10px]" style={{ color: 'var(--color-text-dim)' }}>
          {completedPhases} of {phases.length} phases complete
        </div>
      </div>

      {/* Current sub-phase */}
      {subPhase && (
        <div className="p-2 rounded-lg" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal-dim)' }}>
          <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--color-teal-dim)' }}>Current Stage</p>
          <p className="text-xs font-medium" style={{ color: 'var(--color-teal)' }}>{subPhase}</p>
          {phaseRound > 0 && (
            <p className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-dim)' }}>Round {phaseRound} in phase</p>
          )}
        </div>
      )}

      {/* Divider */}
      <div style={{ borderTop: '1px solid var(--color-border)' }} />

      {/* Documents */}
      <div>
        <h3 className="text-xs font-bold mb-2" style={{ color: 'var(--color-text-dim)' }}>Documents</h3>
        {documents.map((doc) => {
          const status = getDocStatus(doc.id);
          const styles = statusStyles[status];
          return (
            <div key={doc.id} className="p-2 rounded-lg mb-2 text-xs" style={{ background: 'var(--color-navy)', ...styles, opacity: styles.opacity }}>
              <p className="font-medium truncate" style={{ color: styles.color }}>{doc.filename}</p>
              <div className="flex justify-between mt-0.5">
                <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>{doc.filetype}</span>
                <span className="text-[10px]" style={{ color: status === 'current' ? 'var(--color-teal)' : 'var(--color-text-dim)' }}>{statusLabels[status]}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Current phase focus */}
      {currentPhase && (
        <>
          <div style={{ borderTop: '1px solid var(--color-border)' }} />
          <div>
            <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>Phase Focus</p>
            <p className="text-xs" style={{ color: 'var(--color-text)', lineHeight: '1.5' }}>{currentPhase.focus_question}</p>
          </div>
        </>
      )}
    </div>
  );
}
