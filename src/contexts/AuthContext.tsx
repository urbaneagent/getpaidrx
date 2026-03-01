import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  name: string;
  pharmacyName?: string;
  plan: 'free' | 'pro' | 'enterprise';
  claimsUsed: number;
  comparisonsUsed: number;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string, pharmacyName?: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for existing session
    const stored = localStorage.getItem('getpaidrx_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem('getpaidrx_user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, _password: string) => {
    // For MVP: simple local auth. Replace with real backend auth later.
    setIsLoading(true);
    await new Promise(r => setTimeout(r, 500)); // Simulate API call
    
    const existingUsers = JSON.parse(localStorage.getItem('getpaidrx_users') || '{}');
    const existingUser = existingUsers[email];
    
    if (!existingUser) {
      setIsLoading(false);
      throw new Error('No account found with that email. Please sign up first.');
    }

    const newUser: User = {
      id: existingUser.id,
      email,
      name: existingUser.name,
      pharmacyName: existingUser.pharmacyName,
      plan: existingUser.plan || 'free',
      claimsUsed: existingUser.claimsUsed || 0,
      comparisonsUsed: existingUser.comparisonsUsed || 0,
    };
    
    setUser(newUser);
    localStorage.setItem('getpaidrx_user', JSON.stringify(newUser));
    setIsLoading(false);
  }, []);

  const signup = useCallback(async (email: string, _password: string, name: string, pharmacyName?: string) => {
    setIsLoading(true);
    await new Promise(r => setTimeout(r, 500));
    
    const newUser: User = {
      id: crypto.randomUUID(),
      email,
      name,
      pharmacyName,
      plan: 'free',
      claimsUsed: 0,
      comparisonsUsed: 0,
    };
    
    // Store in "database"
    const existingUsers = JSON.parse(localStorage.getItem('getpaidrx_users') || '{}');
    existingUsers[email] = newUser;
    localStorage.setItem('getpaidrx_users', JSON.stringify(existingUsers));
    
    setUser(newUser);
    localStorage.setItem('getpaidrx_user', JSON.stringify(newUser));
    setIsLoading(false);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem('getpaidrx_user');
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      login,
      signup,
      logout,
      isAuthenticated: !!user,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
