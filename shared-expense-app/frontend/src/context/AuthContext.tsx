import React, { createContext, useContext, useState, useEffect } from 'react';
import * as authApi from '../api/auth';

interface AuthContextType {
  user: authApi.UserInfo | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginAction: (username: string, password: string) => Promise<void>;
  logoutAction: () => void;
  updateUserMetadata: (id: number) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<authApi.UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Rehydrate auth state from sessionStorage
    const storedToken = sessionStorage.getItem('spreewise_token');
    const storedUser = sessionStorage.getItem('spreewise_user');
    
    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  const loginAction = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const userInfo = await authApi.login(username, password);
      const generatedToken = btoa(`${username}:${password}`);
      
      setToken(generatedToken);
      setUser(userInfo);
      
      sessionStorage.setItem('spreewise_token', generatedToken);
      sessionStorage.setItem('spreewise_user', JSON.stringify(userInfo));
    } catch (error) {
      setIsLoading(false);
      throw error;
    }
    setIsLoading(false);
  };

  const logoutAction = () => {
    setToken(null);
    setUser(null);
    sessionStorage.removeItem('spreewise_token');
    sessionStorage.removeItem('spreewise_user');
    sessionStorage.removeItem('spreewise_active_group_id');
  };

  const updateUserMetadata = (id: number) => {
    if (user) {
      const updatedUser = { ...user, id };
      setUser(updatedUser);
      sessionStorage.setItem('spreewise_user', JSON.stringify(updatedUser));
    }
  };

  const isAuthenticated = !!token;

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, isLoading, loginAction, logoutAction, updateUserMetadata }}>
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
