import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../store/sessionStore';
import { useAuthStore } from '../store/authStore';
import LoadingDots from '../components/shared/LoadingDots';

export default function Sessions() {
  const { sessions, loading, fetchSessions, createSession, deleteSession } = useSessionStore();
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleNew = async () => {
    const session = await createSession({ name: 'New Session' });
    navigate(`/canvas/${session.id}`);
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'complete': return '#2dd4bf';
      case 'running': return '#fbbf24';
      case 'error': return '#f87171';
      default: return '#94a3b8';
    }
  };

  return (
    <div className="min-h-screen p-8" style={{ background: 'var(--color-navy)' }}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--color-teal)' }}>Symposium</h1>
            <p className="text-sm" style={{ color: 'var(--color-text-dim)' }}>Multi-agent brainstorming sessions</p>
          </div>
          <div className="flex gap-3">
            <button onClick={handleNew} className="px-4 py-2 rounded-lg font-medium text-sm" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>+ New Session</button>
            <button onClick={() => { logout(); navigate('/login'); }} className="px-4 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Logout</button>
          </div>
        </div>

        {loading ? (
          <div className="py-8 flex justify-center"><LoadingDots label="Loading sessions" /></div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
            <p className="text-lg mb-2" style={{ color: 'var(--color-text-dim)' }}>No sessions yet</p>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-dim)' }}>Create your first brainstorming session</p>
            <button onClick={handleNew} className="px-4 py-2 rounded-lg font-medium text-sm" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>+ New Session</button>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-4 rounded-lg cursor-pointer hover:opacity-90 transition-opacity" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }} onClick={() => s.status === 'complete' ? navigate(`/results/${s.id}`) : navigate(`/canvas/${s.id}`)}>
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full" style={{ background: statusColor(s.status) }} />
                  <div>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs" style={{ color: 'var(--color-text-dim)' }}>{s.mode === 'product' ? 'Product Discussion' : 'Problem Discussion'} · {new Date(s.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-2 py-1 rounded" style={{ background: 'var(--color-navy)', color: statusColor(s.status) }}>{s.status}</span>
                  <button onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }} className="text-xs px-2 py-1 rounded hover:bg-red-900/30 text-red-400">Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
