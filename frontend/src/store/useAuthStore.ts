import { create } from 'zustand';
import type { User, LoginRequest, RegisterRequest } from '@/types';
import { apiClient, setTokens, clearTokens, getAccessToken } from '@/api/client';

interface AuthState {
  // 状态
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;

  // 认证操作
  login: (data: LoginRequest) => Promise<boolean>;
  register: (data: RegisterRequest) => Promise<boolean>;
  logout: () => Promise<void>;
  fetchCurrentUser: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // 初始状态
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  // 基础操作
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setError: (error) => set({ error }),
  setLoading: (loading) => set({ isLoading: loading }),

  // 登录
  login: async (data: LoginRequest): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/api/auth/login', data);
      if (response.data.success) {
        const { user, access_token, refresh_token } = response.data.data;
        setTokens(access_token, refresh_token);
        set({ user, isAuthenticated: true, isLoading: false });
        return true;
      } else {
        set({ error: response.data.message || '登录失败', isLoading: false });
        return false;
      }
    } catch (error: any) {
      const message = error.response?.data?.message || '登录失败，请检查用户名和密码';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  // 注册
  register: async (data: RegisterRequest): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/api/auth/register', data);
      if (response.data.success) {
        const { user, access_token, refresh_token } = response.data.data;
        setTokens(access_token, refresh_token);
        set({ user, isAuthenticated: true, isLoading: false });
        return true;
      } else {
        set({ error: response.data.message || '注册失败', isLoading: false });
        return false;
      }
    } catch (error: any) {
      const message = error.response?.data?.message || '注册失败，请稍后重试';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  // 登出
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/api/auth/logout');
    } catch (error) {
      // 忽略登出错误
      console.error('Logout error:', error);
    } finally {
      clearTokens();
      set({ user: null, isAuthenticated: false });
    }
  },

  // 获取当前用户
  fetchCurrentUser: async (): Promise<void> => {
    set({ isLoading: true });
    try {
      const response = await apiClient.get('/api/auth/me');
      if (response.data.success) {
        set({ user: response.data.data.user, isAuthenticated: true, isLoading: false });
      } else {
        set({ user: null, isAuthenticated: false, isLoading: false });
      }
    } catch (error) {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  // 检查认证状态（应用启动时调用）
  checkAuth: async (): Promise<boolean> => {
    const token = getAccessToken();
    if (!token) {
      set({ user: null, isAuthenticated: false });
      return false;
    }

    try {
      const response = await apiClient.get('/api/auth/me');
      if (response.data.success) {
        set({ user: response.data.data.user, isAuthenticated: true });
        return true;
      } else {
        clearTokens();
        set({ user: null, isAuthenticated: false });
        return false;
      }
    } catch (error) {
      clearTokens();
      set({ user: null, isAuthenticated: false });
      return false;
    }
  },
}));
