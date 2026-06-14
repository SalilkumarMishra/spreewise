import React, { createContext, useContext, useState, useEffect } from 'react';
import * as authApi from '../api/auth';

interface AuthContextType {
  user: authApi.UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginAction: (username: string, password: string) => Promise<void>;
  registerAction: (
    fullName: string,
    username: string,
    email: string,
    password: string,
    confirmPassword: string
  ) => Promise<void>;
  logoutAction: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEYS = {
  ACCESS: 'spreewise_access_token',
  REFRESH: 'spreewise_refresh_token',
  USER: 'spreewise_user',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<authApi.UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Rehydrate auth state from sessionStorage on app start
    const storedUser = sessionStorage.getItem(STORAGE_KEYS.USER);
    const storedAccess = sessionStorage.getItem(STORAGE_KEYS.ACCESS);

    if (storedAccess && storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        sessionStorage.clear();
      }
    }
    setIsLoading(false);
  }, []);

  const _storeSession = (tokens: authApi.AuthTokens, userInfo: authApi.UserInfo) => {
    sessionStorage.setItem(STORAGE_KEYS.ACCESS, tokens.access);
    sessionStorage.setItem(STORAGE_KEYS.REFRESH, tokens.refresh);
    sessionStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userInfo));
    setUser(userInfo);
  };

  const loginAction = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const data = await authApi.login(username, password);
      // Fetch full user profile after login
      sessionStorage.setItem(STORAGE_KEYS.ACCESS, data.access);
      sessionStorage.setItem(STORAGE_KEYS.REFRESH, data.refresh);
      const userInfo = await authApi.getMe();
      _storeSession(data, userInfo);
    } finally {
      setIsLoading(false);
    }
  };

  const registerAction = async (
    fullName: string,
    username: string,
    email: string,
    password: string,
    confirmPassword: string
  ) => {
    setIsLoading(true);
    try {
      const data = await authApi.register(fullName, username, email, password, confirmPassword);
      _storeSession(data, data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logoutAction = async () => {
    try {
      const refreshToken = sessionStorage.getItem(STORAGE_KEYS.REFRESH);
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch {
      // Swallow errors
    } finally {
      setUser(null);
      sessionStorage.removeItem(STORAGE_KEYS.ACCESS);
      sessionStorage.removeItem(STORAGE_KEYS.REFRESH);
      sessionStorage.removeItem(STORAGE_KEYS.USER);
      sessionStorage.removeItem('spreewise_active_group_id');
    }
  };

  const isAuthenticated = !!user && !!sessionStorage.getItem(STORAGE_KEYS.ACCESS);

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated, isLoading, loginAction, registerAction, logoutAction }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
