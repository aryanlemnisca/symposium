import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSessionStore } from '../store/sessionStore';
import MarkdownRenderer from '../components/shared/MarkdownRenderer';
import SaveTemplateModal from '../components/shared/SaveTemplateModal';
import LoadingDots from '../components/shared/LoadingDots';

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession, updateSession } = useSessionStore();
  const [activeTab, setActiveTab] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [showTemplateModal, setShowTemplateModal] = useState(false);

  useEffect(() => {
    if (id) fetchSession(id);
  }, [id, fetchSession]);

  useEffect(() => {
    if (currentSession?.outputs) {
      const tabs = Object.keys(currentSession.outputs);
      if (tabs.length > 0 && !activeTab) {
        const defaultTab = tabs.find((t) => t.includes('executive'))
          || tabs.find((t) => t.includes('verdict'))
          || tabs.find((t) => t.includes('prd') || t.includes('conclusion'))
          || tabs[0];
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
    return <LoadingDots centered label="Loading results" />;
  }

  const outputs = currentSession.outputs || {};
  const tabs = Object.keys(outputs);
  const sortedTabs = [...tabs].sort((a, b) => {
    const order = (t: string) => {
      if (t.includes('executive')) return 0;
      if (t.includes('verdict')) return 1;
      if (t.includes('synthesis')) return 2;
      if (t.includes('prd') && !t.includes('panel')) return 3;
      if (t.includes('conclusion')) return 2;
      if (t.includes('phase')) return 4;
      if (t.includes('prd_panel')) return 5;
      if (t.includes('transcript')) return 9;
      return 6;
    };
    const diff = order(a) - order(b);
    if (diff !== 0) return diff;
    return a.localeCompare(b);
  });

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-navy)' }}>
      <div className="flex items-center justify-between px-8 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div>
          <button onClick={() => navigate('/sessions')} className="text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>&larr; Sessions</button>
          {editingName ? (
            <input
              autoFocus
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              onBlur={async () => {
                if (id && nameValue.trim() && nameValue !== currentSession.name) {
                  await updateSession(id, { name: nameValue.trim() });
                }
                setEditingName(false);
              }}
              onKeyDown={async (e) => {
                if (e.key === 'Enter') {
                  if (id && nameValue.trim() && nameValue !== currentSession.name) {
                    await updateSession(id, { name: nameValue.trim() });
                  }
                  setEditingName(false);
                }
                if (e.key === 'Escape') setEditingName(false);
              }}
              className="text-lg font-bold bg-transparent outline-none w-full"
              style={{ color: 'var(--color-teal)', borderBottom: '1px solid var(--color-teal)' }}
            />
          ) : (
            <h1
              className="text-lg font-bold cursor-pointer hover:opacity-80"
              style={{ color: 'var(--color-teal)' }}
              onClick={() => { setNameValue(currentSession.name); setEditingName(true); }}
              title="Click to rename"
            >{currentSession.name}</h1>
          )}
          <p className="text-xs" style={{ color: 'var(--color-text-dim)' }}>{currentSession.mode === 'product' ? 'Product Discussion' : currentSession.mode === 'stress_test' ? 'Stress Test Review' : 'Problem Discussion'} · Completed {currentSession.completed_at ? new Date(currentSession.completed_at).toLocaleString() : ''}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowTemplateModal(true)} className="px-3 py-2 rounded-lg text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Save Template</button>
          <button onClick={() => navigate(`/canvas/${id}`)} className="px-3 py-2 rounded-lg text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Re-run</button>
          <button onClick={handleDownloadZip} className="px-3 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Download ZIP</button>
        </div>
      </div>

      <div className="flex px-8 pt-4 gap-1" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {sortedTabs.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className="px-4 py-2 text-sm rounded-t-lg" style={{
            background: activeTab === tab ? 'var(--color-navy-light)' : 'transparent',
            color: activeTab === tab ? 'var(--color-teal)' : tab.includes('verdict') ? '#fbbf24' : 'var(--color-text-dim)',
            borderBottom: activeTab === tab ? '2px solid var(--color-teal)' : '2px solid transparent',
            fontWeight: tab.includes('verdict') ? 'bold' : 'normal',
          }}>
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
