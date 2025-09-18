'use client';

import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { login, loading, error, isAuthenticated } = useAuth();
  const router = useRouter();

  // Redirect to chat if already authenticated
  useEffect(() => {
    if (isAuthenticated()) {
      router.push('/chat');
    }
  }, [isAuthenticated, router]);

  const handleLogin = () => {
    login();
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary/5 via-secondary/5 to-background">
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center min-h-screen text-center">
        <div className="space-y-8 max-w-4xl">
          <div className="space-y-4">
            <h1 className="text-6xl md:text-7xl font-bold text-primary tracking-tight">
              Charlotte
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
              Using AI to make UNC employee workflow simple and easy. Just ask away and with 99.9% guarantee you'll find what you want instead of going to your team or browsing endless files in your department's shared drive.
            </p>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-8">
            <Button 
              onClick={handleLogin}
              disabled={loading}
              size="lg" 
              className="text-lg px-8 py-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Signing in..." : "Login with UNC Account"}
            </Button>
          </div>
          
          {error && (
            <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
              <p className="text-destructive">{error}</p>
            </div>
          )}
          
          <div className="pt-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
              <div className="space-y-3">
                <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                  <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold">Instant Answers</h3>
                <p className="text-muted-foreground">Get immediate responses to your questions without waiting</p>
              </div>
              
              <div className="space-y-3">
                <div className="w-16 h-16 mx-auto bg-secondary/10 rounded-full flex items-center justify-center">
                  <svg className="w-8 h-8 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold">Accurate Results</h3>
                <p className="text-muted-foreground">AI-powered search across all UNC resources and documents</p>
              </div>
              
              <div className="space-y-3">
                <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                  <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold">Secure Access</h3>
                <p className="text-muted-foreground">Protected by UNC authentication with role-based permissions</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}