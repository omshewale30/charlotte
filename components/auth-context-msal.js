'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useMsal } from "@azure/msal-react";
import { loginRequest } from '../lib/auth-config';

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
  const { instance, accounts } = useMsal();
  const router = useRouter();

  // Check authentication status on mount and when accounts change
  useEffect(() => {
    const account = accounts[0];
    if (account) {
      setUser({
        id: account.localAccountId,
        email: account.username,
        name: account.name,
        given_name: account.idTokenClaims?.given_name,
        family_name: account.idTokenClaims?.family_name,
        job_title: account.idTokenClaims?.jobTitle,
        tenant_id: account.tenantId
      });
    } else {
      setUser(null);
    }
    setLoading(false);
  }, [accounts]);

  const login = async () => {
    try {
      setLoading(true);
      setError(null);

      // Try silent login first
      const silentRequest = {
        ...loginRequest,
        account: accounts[0],
      };

      try {
        await instance.acquireTokenSilent(silentRequest);
      } catch (silentError) {
        // If silent login fails, use popup
        await instance.loginPopup(loginRequest);
      }
    } catch (error) {
      console.error('Login failed:', error);
      setError(error.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      setLoading(true);
      
      // Sign out from MSAL
      await instance.logoutPopup({
        postLogoutRedirectUri: "/",
        mainWindowRedirectUri: "/"
      });
      
      setUser(null);
      router.push('/');
    } catch (error) {
      console.error('Logout failed:', error);
      setError(error.message || 'Logout failed');
    } finally {
      setLoading(false);
    }
  };

  const getAccessToken = async () => {
    try {
      const account = accounts[0];
      if (!account) {
        throw new Error('No account found');
      }

      const silentRequest = {
        ...loginRequest,
        account: account,
      };

      const response = await instance.acquireTokenSilent(silentRequest);
      return response.accessToken;
    } catch (error) {
      console.error('Failed to get access token:', error);
      
      // If silent token acquisition fails, try popup
      try {
        const response = await instance.acquireTokenPopup(loginRequest);
        return response.accessToken;
      } catch (popupError) {
        console.error('Popup token acquisition failed:', popupError);
        throw popupError;
      }
    }
  };

  const getAuthHeaders = async () => {
    try {
      const token = await getAccessToken();
      return { 'Authorization': `Bearer ${token}` };
    } catch (error) {
      console.error('Failed to get auth headers:', error);
      return {};
    }
  };

  const isAuthenticated = () => {
    return !!user && accounts.length > 0;
  };

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    getAuthHeaders,
    getAccessToken,
    isAuthenticated,
    setError
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};