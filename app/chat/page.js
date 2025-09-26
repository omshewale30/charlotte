'use client';

import ChatInterface from "@/components/chat-interface";
import Header from "@/components/header";
import ProtectedRoute from "@/components/protected-route";
import { useAuth } from "@/components/auth-context-msal";

export default function ChatPage() {
  const { user } = useAuth();

  return (
    <ProtectedRoute>
      <main className="flex min-h-screen flex-col bg-background">
        <Header />
        <div className="flex-1 container mx-auto px-4 py-6 max-w-4xl">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-primary mb-2">Welcome to Charlotte</h1>
            {user && (
              <p className="text-muted-foreground">
                Hello {user.given_name || user.name}! Ask me anything about UNC resources.
              </p>
            )}
          </div>
          <ChatInterface />
        </div>
      </main>
    </ProtectedRoute>
  );
}