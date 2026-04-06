import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

export function useInlineSuggestion(text: string, debounceMs: number = 800) {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setSuggestion(null);
    if (!text || text.length < 20) return;

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.post<{ suggestion: string }>('/suggest/inline', { text });
        if (res.suggestion && res.suggestion !== 'NONE') {
          setSuggestion(res.suggestion);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }, debounceMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [text, debounceMs]);

  const dismiss = () => setSuggestion(null);

  return { suggestion, loading, dismiss };
}


export function useReview() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const review = async (text: string, type: 'problem_statement' | 'persona' | 'stress_test_problem' = 'problem_statement', otherAgents: unknown[] = []): Promise<Record<string, unknown> | null> => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post<{ result: Record<string, unknown> }>('/suggest/review', {
        text,
        review_type: type,
        other_agents: otherAgents,
      });
      setResult(res.result);
      return res.result;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { review, loading, result, clearResult: () => setResult(null) };
}
