'use client';

import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from '../lib/auth-config';
import { AuthProvider } from './auth-context-msal';

export default function MsalProviderWrapper({ children }) {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthProvider>
        {children}
      </AuthProvider>
    </MsalProvider>
  );
}