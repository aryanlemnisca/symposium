import type { UploadedDocument, Phase } from '../../store/sessionStore';

interface Props {
  documents: UploadedDocument[];
  phases: Phase[];
  currentPhaseIndex: number;
}

export default function DocumentSidebar({ documents, phases, currentPhaseIndex }: Props) {
  const currentPhase = phases[currentPhaseIndex];
  const currentDocIds = new Set(currentPhase?.document_ids || []);
  const previousDocIds = new Set(
    phases.slice(0, currentPhaseIndex).flatMap((p) => p.document_ids || [])
  );

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
    <div className="h-full overflow-y-auto p-3" style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}>
      <h3 className="text-xs font-bold mb-3" style={{ color: 'var(--color-teal)' }}>Documents</h3>

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
  );
}
