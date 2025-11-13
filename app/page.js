'use client';

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/components/auth-context-msal";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Navigation from "@/components/navigation";

export default function Home() {
  const { login, loading, error, isAuthenticated } = useAuth();
  const router = useRouter();

  // Redirect to chat if already authenticated
  useEffect(() => {
    if (isAuthenticated()) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  const handleLogin = () => {
    login();
  };

  const features = [
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      ),
      title: "AI-Powered Chat",
      description: "Ask questions about UNC resources, policies, and procedures. Our Azure AI Foundry agent provides intelligent, context-aware answers with conversation memory."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      ),
      title: "EDI Transaction Search",
      description: "Search EDI transactions using natural language. Find payments by amount, date, originator, receiver, or trace number with intelligent query understanding."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
      title: "Financial Report Analysis",
      description: "Analyze EDI and AlignRx reports with AI-powered insights. Get summaries, daily totals, breakdowns by originator/receiver, and automated overviews for any date range."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      ),
      title: "Report Upload & Processing",
      description: "Upload EDI and AlignRx reports (PDF, Excel, CSV) for automatic parsing and indexing. Reports are processed, validated, and made searchable instantly."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      title: "Data Export",
      description: "Export analyzed financial data to Excel with comprehensive breakdowns. Download transaction summaries, daily totals, and detailed reports for further analysis."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      title: "Conversation Memory",
      description: "Unified conversation tracking across all systems. Your chat history, EDI queries, and analysis requests are remembered for context-aware responses."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      ),
      title: "Secure UNC Authentication",
      description: "Protected by Microsoft Entra ID (Azure AD) authentication. Only authorized UNC employees can access the system with role-based permissions."
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      {/* Hero Section */}
      <section className="hero-gradient pt-24 pb-20 md:pt-32 md:pb-28 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-6xl mx-auto">
            <div className="text-center space-y-10">
              {/* Main Headline */}
              <div className="space-y-8">
                  <h1 className="fade-in-up text-5xl md:text-6xl lg:text-7xl xl:text-8xl font-bold text-foreground tracking-tight leading-tight">
                    Your UNC Workflow,
                    <br />
                    <span className="gradient-text">AI-Powered.</span>
                  </h1>
                  <p className="fade-in-up-delay-1 text-xl md:text-2xl lg:text-3xl text-muted-foreground max-w-4xl mx-auto leading-relaxed font-light">
                    Meet <span className="font-semibold text-primary">Charlotte</span>: 
                    The single platform to search policies, analyze financial reports, and get instant answers.
                  </p>
                </div>
              
              {/* CTA Button */}
              <div className="fade-in-up-delay-2 pt-6">
                <Button 
                  onClick={handleLogin}
                  disabled={loading}
                  size="lg" 
                  className="btn-primary text-lg md:text-xl px-12 py-7 md:px-16 md:py-8 rounded-xl shadow-lg disabled:opacity-50 disabled:cursor-not-allowed bg-[#4B9CD3] hover:bg-[#2B6FA6] text-white font-semibold"
                >
                  {loading ? "Signing in..." : "Login with UNC Account"}
                </Button>
              </div>
              
              {/* Error Message */}
              {error && (
                <div className="fade-in-up-delay-3 mt-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg max-w-md mx-auto backdrop-blur-sm">
                  <p className="text-destructive font-medium">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

       {/* Features Section */}
      <section id="features" className="section-spacing bg-gradient-to-b from-background via-muted/20 to-background">
        <div className="container mx-auto px-4">
          <div className="max-w-7xl mx-auto">
            <Card className="feature-overview-card border-2 border-primary/20 shadow-2xl">
              <CardHeader className="text-center pb-8 pt-12 px-8">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] mb-6 shadow-lg">
                  <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h2 className="fade-in-up text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 tracking-tight">
                  Powerful Features for{' '}
                  <span className="gradient-text">UNC Employees</span>
                </h2>
                <p className="fade-in-up-delay-1 text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
                  Everything you need to streamline your workflow and find information quickly
                </p>
              </CardHeader>
              <CardContent className="px-8 pb-12">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {features.map((feature, index) => (
                    <div key={index} className="text-center p-6 rounded-xl bg-card/60 backdrop-blur-sm border border-primary/10 hover:border-primary/30 transition-all duration-300 hover-lift">
                      <div className="text-sm font-semibold text-primary mb-2">
                        {String(index + 1).padStart(2, '0')}
                      </div>
                      <h3 className="text-lg font-bold text-foreground mb-2">
                        {feature.title}
                      </h3>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {feature.description}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>



      {/* About Section */}
      <section id="about" className="section-spacing bg-gradient-to-b from-background via-muted/10 to-background">
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="fade-in-up text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 tracking-tight">
                Built for <span className="gradient-text">UNC</span>, By UNC
              </h2>
              <div className="w-24 h-1 bg-gradient-to-r from-transparent via-[#4B9CD3] to-transparent mx-auto mb-8"></div>
            </div>
            
            <div className="fade-in-up-delay-1 space-y-8">
              <Card className="border-2 border-primary/10 bg-card/60 backdrop-blur-sm shadow-xl p-8 md:p-12 hover:border-primary/20 transition-all duration-300">
                <CardContent className="space-y-6 text-lg md:text-xl text-muted-foreground leading-relaxed">
                  <p className="text-foreground/90">
                    Charlotte is designed specifically for <span className="font-semibold text-primary">University of North Carolina</span> employees, 
                    understanding the unique challenges and workflows of academic and administrative staff.
                  </p>
                  <div className="h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent my-6"></div>
                  <p className="text-foreground/90">
                    Our AI system is completely <span className="font-semibold text-primary">in-house</span> and the data does not leave the UNC network. This ensures that every answer is relevant, accurate, and tailored to your needs.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>


      {/* Footer */}
      <footer className="py-16 md:py-20 bg-gradient-to-b from-background to-secondary/30 border-t border-primary/10">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col md:flex-row justify-between items-center space-y-6 md:space-y-0">
              <div className="flex items-center space-x-3 group cursor-pointer">
                <div className="w-12 h-12 bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] rounded-xl flex items-center justify-center shadow-lg transition-all duration-300 group-hover:scale-110 group-hover:shadow-xl">
                  <span className="text-white font-bold text-xl">C</span>
                </div>
                <span className="text-2xl font-bold text-foreground">Charlotte</span>
              </div>
              <div className="text-center md:text-right">
                <p className="text-base text-muted-foreground font-medium">
                  © 2024 Charlotte. Built for <span className="text-primary font-semibold">UNC employees</span>.
                </p>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}