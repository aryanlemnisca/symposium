import { create } from 'zustand';
import { api } from '../api/client';

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('symposium_token'),
  isAuthenticated: !!localStorage.getItem('symposium_token'),

  login: async (password: string) => {
    const { token } = await api.post<{ token: string }>('/auth/login', { password });
    localStorage.setItem('symposium_token', token);
    set({ token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('symposium_token');
    set({ token: null, isAuthenticated: false });
  },

  checkAuth: () => {
    const token = localStorage.getItem('symposium_token');
    set({ token, isAuthenticated: !!token });
  },
}));
