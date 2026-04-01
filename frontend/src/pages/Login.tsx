import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Login() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(password);
      navigate('/sessions');
    } catch {
      setError('Wrong password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)' }}>
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm p-8 rounded-xl"
        style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}
      >
        <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--color-teal)' }}>
          Symposium
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--color-text-dim)' }}>
          Multi-agent brainstorming canvas
        </p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter password"
          autoFocus
          className="w-full px-4 py-3 rounded-lg text-sm mb-4 outline-none focus:ring-2"
          style={{
            background: 'var(--color-navy)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
          }}
        />

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-3 rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
          style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
        >
          {loading ? 'Signing in...' : 'Enter'}
        </button>
      </form>
    </div>
  );
}
