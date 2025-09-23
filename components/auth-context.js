'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

const AuthContext = createContext({});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const router = useRouter();

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const sessionId = localStorage.getItem('session_id');
      
      if (!sessionId) {
        setLoading(false);
        return;
      }

      const response = await fetch(`${API_BASE}/auth/status`, {
        headers: {
          'Authorization': `Bearer ${sessionId}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.authenticated) {
        setUser(data.user);
      } else {
        // Clear invalid session
        localStorage.removeItem('session_id');
        setUser(null);
      }
    } catch (error) {
      console.error('Auth status check failed:', error);
      localStorage.removeItem('session_id');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get auth URL from backend
      const response = await fetch(`${API_BASE}/auth/login`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to get auth URL');
      }

      // Store state for verification
      localStorage.setItem('auth_state', data.state);

      // Redirect to Microsoft login
      window.location.href = data.auth_url;
    } catch (error) {
      console.error('Login failed:', error);
      setError(error.message);
      setLoading(false);
    }
  };

  const handleAuthCallback = async (code, state) => {
    try {
      setLoading(true);
      setError(null);

      // Verify state matches what we stored
      const storedState = localStorage.getItem('auth_state');
      if (state !== storedState) {
        throw new Error('Invalid state parameter');
      }

      // Exchange code for session
      const response = await fetch(`${API_BASE}/auth/callback?code=${code}&state=${state}`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Authentication failed: ${response.status}`);
      }

      const data = await response.json();
      console.log('Auth callback response:', data);

      if (data.success && data.session_id && data.user) {
        // Store session
        localStorage.setItem('session_id', data.session_id);
        localStorage.removeItem('auth_state');
        
        setUser(data.user);
        
        // Small delay to ensure state is updated
        setTimeout(() => {
          router.push('/chat');
        }, 100);
      } else {
        throw new Error('Invalid authentication response format');
      }
    } catch (error) {
      console.error('Auth callback failed:', error);
      setError(error.message);
      localStorage.removeItem('auth_state');
      localStorage.removeItem('session_id');
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      const sessionId = localStorage.getItem('session_id');
      
      if (sessionId) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${sessionId}`,
            'Content-Type': 'application/json',
          },
        });
      }
    } catch (error) {
      console.error('Logout request failed:', error);
    } finally {
      // Clear local state regardless of API call success
      localStorage.removeItem('session_id');
      localStorage.removeItem('auth_state');
      setUser(null);
      router.push('/');
    }
  };

  const getAuthHeaders = () => {
    const sessionId = localStorage.getItem('session_id');
    return sessionId ? { 'Authorization': `Bearer ${sessionId}` } : {};
  };

  const isAuthenticated = () => {
    return !!user && !!localStorage.getItem('session_id');
  };

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    handleAuthCallback,
    checkAuthStatus,
    getAuthHeaders,
    isAuthenticated,
    setError,
    setUser
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};