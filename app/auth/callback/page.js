'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMsal } from "@azure/msal-react";

export default function AuthCallback() {
  const router = useRouter();
  const { instance, accounts } = useMsal();
  const [loading, setLoading] = useState(true);
  const [localError, setLocalError] = useState(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // MSAL automatically handles the authentication response
        // Check if we have authenticated accounts
        if (accounts && accounts.length > 0) {
          // Authentication successful, redirect to chat
          router.push('/dashboard');
        } else {
          // No accounts means authentication failed or in progress
          setTimeout(() => {
            if (accounts.length === 0) {
              setLocalError('Authentication failed - no account found');
            }
          }, 2000); // Give MSAL some time to process
        }
      } catch (error) {
        console.error('Callback processing error:', error);
        setLocalError(error.message);
      } finally {
        setLoading(false);
      }
    };

    handleCallback();
  }, [accounts, router]);

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