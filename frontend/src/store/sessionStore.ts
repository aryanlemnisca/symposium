import { create } from 'zustand';
import { api } from '../api/client';

export interface AgentConfig {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  canvas_position: { x: number; y: number };
}

export interface SessionSettings {
  max_rounds: number;
  temperature: number;
  gate_start_round: number;
  overseer_interval: number;
  min_rounds_before_convergence: number;
  prd_panel_rounds: number;
  prd_panel_names?: string[];
  stress_test_min_rounds_per_phase?: number;
}

export interface UploadedDocument {
  id: string;
  filename: string;
  filetype: string;
  content_text: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface Phase {
  number: number;
  name: string;
  document_ids: string[];
  focus_question: string;
  key_subquestions: string[];
  artifact_schema: string[];
  rationale: string;
  status: 'pending' | 'active' | 'complete';
  start_round: number | null;
  end_round: number | null;
  artifact: string | null;
  confirmed: string[];
  contested: string[];
  open_questions: string[];
}

export interface SessionData {
  id: string;
  name: string;
  mode: string;
  problem_statement: string;
  agents: AgentConfig[];
  settings: SessionSettings;
  status: string;
  created_at: string;
  completed_at: string | null;
  canvas_state: Record<string, unknown>;
  document_ids: string[];
  outputs: Record<string, string> | null;
  phases: Phase[] | null;
  uploaded_documents: UploadedDocument[] | null;
  stress_review_instructions: string | null;
}

interface SessionState {
  sessions: SessionData[];
  currentSession: SessionData | null;
  loading: boolean;
  fetchSessions: () => Promise<void>;
  fetchSession: (id: string) => Promise<void>;
  createSession: (data: Partial<SessionData>) => Promise<SessionData>;
  updateSession: (id: string, data: Partial<SessionData>) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  setCurrentSession: (session: SessionData | null) => void;
}

export const useSessionStore = create<SessionState>((set, _get) => ({
  sessions: [],
  currentSession: null,
  loading: false,

  fetchSessions: async () => {
    set({ loading: true });
    const sessions = await api.get<SessionData[]>('/sessions');
    set({ sessions, loading: false });
  },

  fetchSession: async (id: string) => {
    const session = await api.get<SessionData>(`/sessions/${id}`);
    set({ currentSession: session });
  },

  createSession: async (data) => {
    const session = await api.post<SessionData>('/sessions', {
      name: data.name || 'New Session',
      mode: data.mode || 'product',
      problem_statement: data.problem_statement || '',
      agents: data.agents || [],
      settings: data.settings || {},
      canvas_state: data.canvas_state || {},
    });
    set((s) => ({ sessions: [session, ...s.sessions] }));
    return session;
  },

  updateSession: async (id, data) => {
    const updated = await api.patch<SessionData>(`/sessions/${id}`, data);
    set((s) => ({
      sessions: s.sessions.map((sess) => (sess.id === id ? updated : sess)),
      currentSession: s.currentSession?.id === id ? updated : s.currentSession,
    }));
  },

  deleteSession: async (id) => {
    await api.delete(`/sessions/${id}`);
    set((s) => ({
      sessions: s.sessions.filter((sess) => sess.id !== id),
      currentSession: s.currentSession?.id === id ? null : s.currentSession,
    }));
  },

  setCurrentSession: (session) => set({ currentSession: session }),
}));
