'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth-context';

export default function AuthCallback() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { setUser, setError } = useAuth();
  const [loading, setLoading] = useState(true);
  const [localError, setLocalError] = useState(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const sessionId = searchParams.get('session_id');
        const success = searchParams.get('success');
        const errorParam = searchParams.get('error');

        if (errorParam) {
          setLocalError(errorParam);
          setError(errorParam);
          return;
        }

        if (success === 'true' && sessionId) {
          // Fetch session data from backend
          const response = await fetch(`${API_BASE}/auth/session/${sessionId}`);
          
          if (!response.ok) {
            throw new Error('Failed to fetch session data');
          }

          const data = await response.json();
          
          // Store session and user data
          localStorage.setItem('session_id', data.session_id);
          setUser(data.user);
          
          // Redirect to chat
          router.push('/chat');
          return;
        }

        // If no session_id or success, something went wrong
        setLocalError('Invalid callback parameters');
        
      } catch (error) {
        console.error('Callback processing error:', error);
        setLocalError(error.message);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };

    handleCallback();
  }, [searchParams, router, setUser, setError, API_BASE]);

  if (localError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center mx-auto">
            <svg className="w-8 h-8 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-destructive">Authentication Failed</h1>
          <p className="text-muted-foreground max-w-md">{localError}</p>
          <button
            onClick={() => window.location.href = '/'}
            className="bg-primary text-primary-foreground px-6 py-3 rounded-lg hover:bg-primary/90 transition-colors"
          >
            Return to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
        <h1 className="text-2xl font-bold">Completing Authentication</h1>
        <p className="text-muted-foreground">Please wait while we sign you in...</p>
      </div>
    </div>
  );
}