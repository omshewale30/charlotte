'use client';

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/components/auth-context-msal";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Navigation from "@/components/navigation";
{/* TODO: Make the UI more engaging and interactive 
  - Add spacing between the features and the about section
*/}

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
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      title: "Instant Answers",
      description: "Get immediate responses to your questions without waiting. Our AI understands context and provides relevant information instantly."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      title: "Accurate Results",
      description: "AI-powered search across all UNC resources and documents. Find exactly what you need with 99.9% accuracy guarantee."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      ),
      title: "Secure Access",
      description: "Protected by UNC authentication with role-based permissions. Your data and conversations are completely secure."
    },
    {
      icon: (
        <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
      title: "Smart Workflow",
      description: "Streamline your daily tasks with intelligent automation. No more endless browsing through shared drives."
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      {/* Hero Section */}
      <section className="hero-gradient pt-20 pb-16">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            <div className="text-center space-y-8">
              {/* Main Headline */}
              <div className="space-y-6">
                <h1 className="fade-in-up text-5xl md:text-6xl lg:text-7xl font-bold text-foreground tracking-tight">
                  Welcome to{' '}
                  <span className="text-primary">Charlotte</span>
                </h1>
                <p className="fade-in-up-delay-1 text-xl md:text-2xl text-muted-foreground max-w-4xl mx-auto leading-relaxed">
                  Using AI to make UNC employee workflow simple and easy. 
                  Just ask away and with 99.9% guarantee you'll find what you want instead of going to your team or browsing endless files in your department's shared drive.
                </p>
              </div>
              
              {/* CTA Button */}
              <div className="fade-in-up-delay-2 pt-8">
                <Button 
                  onClick={handleLogin}
                  disabled={loading}
                  size="lg" 
                  className="btn-primary text-lg px-12 py-6 rounded-xl shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Signing in..." : "Login with UNC Account"}
                </Button>
              </div>
              
              {/* Error Message */}
              {error && (
                <div className="fade-in-up-delay-3 mt-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg max-w-md mx-auto">
                  <p className="text-destructive">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="fade-in-up text-3xl md:text-4xl font-bold text-foreground mb-4">
                Powerful Features for UNC Employees
              </h2>
              <p className="fade-in-up-delay-1 text-lg text-muted-foreground max-w-3xl mx-auto">
                Everything you need to streamline your workflow and find information quickly
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
              {features.map((feature, index) => (
                <Card key={index} className="feature-card fade-in-up-delay-2 hover:shadow-xl border-0 bg-card/50 backdrop-blur-sm">
                  <CardHeader className="text-center pb-4">
                    <div className="w-16 h-16 mx-auto bg-primary/10 rounded-2xl flex items-center justify-center mb-4">
                      {feature.icon}
                    </div>
                    <CardTitle className="text-xl font-semibold text-foreground">
                      {feature.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-center">
                    <CardDescription className="text-muted-foreground leading-relaxed">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="fade-in-up text-3xl md:text-4xl font-bold text-foreground mb-8">
              Built for UNC, By UNC
            </h2>
            <div className="fade-in-up-delay-1 space-y-6 text-lg text-muted-foreground leading-relaxed">
              <p>
                Charlotte is designed specifically for University of North Carolina employees, 
                understanding the unique challenges and workflows of academic and administrative staff.
              </p>
              <p>
                Our AI system has been trained on UNC-specific documents, policies, and procedures, 
                ensuring that every answer is relevant, accurate, and tailored to your needs.
              </p>
              <p>
                Join thousands of UNC employees who have already streamlined their daily workflows 
                and found the information they need in seconds, not hours.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section
      <section className="py-20 bg-primary/5">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <div className="fade-in-up space-y-8">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground">
                Ready to Transform Your Workflow?
              </h2>
              <p className="text-xl text-muted-foreground">
                Start using Charlotte today and experience the future of workplace efficiency.
              </p>
              <Button 
                onClick={handleLogin}
                disabled={loading}
                size="lg" 
                className="btn-primary text-lg px-12 py-6 rounded-xl shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Signing in..." : "Get Started Now"}
              </Button>
            </div>
          </div>
        </div>
      </section> */}

      {/* Contact Section */}
      {/* <section id="contact" className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <div className="fade-in-up space-y-8">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground">
                Need Help Getting Started?
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Our team is here to help you get the most out of Charlotte. 
                Contact us for support, training, or to provide feedback.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12">
                <div className="space-y-4">
                  <div className="w-12 h-12 mx-auto bg-primary/10 rounded-xl flex items-center justify-center">
                    <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">Email Support</h3>
                  <p className="text-muted-foreground">charlotte-support@unc.edu</p>
                </div>
                <div className="space-y-4">
                  <div className="w-12 h-12 mx-auto bg-primary/10 rounded-xl flex items-center justify-center">
                    <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">Response Time</h3>
                  <p className="text-muted-foreground">Within 24 hours</p>
                </div>
                <div className="space-y-4">
                  <div className="w-12 h-12 mx-auto bg-primary/10 rounded-xl flex items-center justify-center">
                    <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">Office Hours</h3>
                  <p className="text-muted-foreground">Mon-Fri 9AM-5PM EST</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section> */}

      {/* Footer */}
      <footer className="py-12 bg-secondary text-secondary-foreground">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col md:flex-row justify-between items-center">
              <div className="flex items-center space-x-2 mb-4 md:mb-0">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                  <span className="text-primary-foreground font-bold text-lg">C</span>
                </div>
                <span className="text-xl font-bold">Charlotte</span>
              </div>
              <div className="text-center md:text-right">
                <p className="text-sm text-secondary-foreground/80">
                  © 2024 Charlotte. Built for UNC employees.
                </p>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}