import { useState, useRef } from 'react';
import type { UploadedDocument } from '../../store/sessionStore';

interface Props {
  documents: UploadedDocument[];
  onChange: (docs: UploadedDocument[]) => void;
}

export default function DocumentUpload({ documents, onChange }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);

    const newDocs = [...documents];
    for (const file of Array.from(files)) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('/api/upload/stress-test', {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('symposium_token')}` },
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          setError(err.detail || 'Upload failed');
          continue;
        }
        const data = await res.json();
        newDocs.push(data.document as UploadedDocument);
      } catch {
        setError(`Failed to upload ${file.name}`);
      }
    }
    onChange(newDocs);
    setUploading(false);
  };

  const removeDoc = (docId: string) => {
    onChange(documents.filter((d) => d.id !== docId));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>Documents</label>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        className="w-full py-6 rounded-lg text-center text-xs cursor-pointer transition-colors"
        style={{ border: '2px dashed var(--color-border)', color: 'var(--color-text-dim)' }}
      >
        {uploading ? 'Uploading...' : 'Drop files here or click to upload'}
        <div className="text-[10px] mt-1">PDF, DOCX, TXT, MD, XLSX, CSV — max 20MB each</div>
      </div>

      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.xlsx,.csv"
        onChange={(e) => handleFiles(e.target.files)}
        className="hidden"
      />

      {error && (
        <p className="text-[10px] mt-1" style={{ color: '#f87171' }}>{error}</p>
      )}

      {documents.length > 0 && (
        <div className="mt-2 space-y-1.5">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between p-2 rounded-lg text-xs" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
              <div className="min-w-0">
                <span className="font-medium truncate block" style={{ color: 'var(--color-text)' }}>{doc.filename}</span>
                <span style={{ color: 'var(--color-text-dim)' }}>{formatSize(doc.size_bytes)} · {doc.filetype}</span>
              </div>
              <button onClick={(e) => { e.stopPropagation(); removeDoc(doc.id); }} className="text-[10px] px-1.5 shrink-0" style={{ color: '#f87171' }}>x</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
