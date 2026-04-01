import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSessionStore } from '../store/sessionStore';
import MarkdownRenderer from '../components/shared/MarkdownRenderer';
import SaveTemplateModal from '../components/shared/SaveTemplateModal';

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession } = useSessionStore();
  const [activeTab, setActiveTab] = useState('');
  const [showTemplateModal, setShowTemplateModal] = useState(true);

  useEffect(() => {
    if (id) fetchSession(id);
  }, [id, fetchSession]);

  useEffect(() => {
    if (currentSession?.outputs) {
      const tabs = Object.keys(currentSession.outputs);
      if (tabs.length > 0 && !activeTab) {
        const defaultTab = tabs.find((t) => t.includes('prd') || t.includes('conclusion')) || tabs[0];
        setActiveTab(defaultTab);
      }
    }
  }, [currentSession, activeTab]);

  const handleDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadZip = async () => {
    if (!id) return;
    const res = await fetch(`/api/sessions/${id}/export?format=zip`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('symposium_token')}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentSession?.name || 'session'}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!currentSession) {
    return <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Loading...</div>;
  }

  const outputs = currentSession.outputs || {};
  const tabs = Object.keys(outputs);

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-navy)' }}>
      <div className="flex items-center justify-between px-8 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div>
          <button onClick={() => navigate('/sessions')} className="text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>&larr; Sessions</button>
          <h1 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>{currentSession.name}</h1>
          <p className="text-xs" style={{ color: 'var(--color-text-dim)' }}>{currentSession.mode === 'product' ? 'Product Discussion' : 'Problem Discussion'} · Completed {currentSession.completed_at ? new Date(currentSession.completed_at).toLocaleString() : ''}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate(`/canvas/${id}`)} className="px-3 py-2 rounded-lg text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Re-run</button>
          <button onClick={handleDownloadZip} className="px-3 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Download ZIP</button>
        </div>
      </div>

      <div className="flex px-8 pt-4 gap-1" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {tabs.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className="px-4 py-2 text-sm rounded-t-lg" style={{ background: activeTab === tab ? 'var(--color-navy-light)' : 'transparent', color: activeTab === tab ? 'var(--color-teal)' : 'var(--color-text-dim)', borderBottom: activeTab === tab ? '2px solid var(--color-teal)' : '2px solid transparent' }}>
            {tab.replace('.md', '').replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      <div className="max-w-4xl mx-auto px-8 py-6">
        {activeTab && outputs[activeTab] && (
          <>
            <div className="flex justify-end mb-4">
              <button onClick={() => handleDownload(activeTab, outputs[activeTab])} className="text-xs px-3 py-1 rounded" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Download {activeTab}</button>
            </div>
            <MarkdownRenderer content={outputs[activeTab]} />
          </>
        )}
      </div>

      {showTemplateModal && currentSession.status === 'complete' && (
        <SaveTemplateModal session={currentSession} onClose={() => setShowTemplateModal(false)} />
      )}
    </div>
  );
}
