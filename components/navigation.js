'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/components/auth-context-msal';

export default function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { login, loading, isAuthenticated } = useAuth();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogin = () => {
    login();
  };

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  return (
    <nav className={`nav-bar ${isScrolled ? 'scrolled' : ''}`}>
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-lg">C</span>
            </div>
            <span className="text-xl font-bold text-foreground">Charlotte</span>
          </div>

          {/* Desktop Navigation Links */}
          <div className="hidden md:flex items-center space-x-8">
            <a href="#features" className="text-muted-foreground hover:text-foreground transition-colors duration-200">
              Features
            </a>
            <a href="#about" className="text-muted-foreground hover:text-foreground transition-colors duration-200">
              About
            </a>
            <a href="#contact" className="text-muted-foreground hover:text-foreground transition-colors duration-200">
              Contact
            </a>
          </div>

          {/* Desktop CTA Button */}
          <div className="hidden md:flex items-center space-x-4">
            {loading ? (
              <Button 
                onClick={handleLogin}
                disabled={true}
                className="btn-primary"
                size="sm"
              >
                {loading ? "Signing in..." : "Login with UNC"}
              </Button>
            ) : (
              <Button 
                onClick={() => window.location.href = '/dashboard'}
                className="btn-primary"
                size="sm"
              >
                Go to Dashboard
              </Button>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={toggleMobileMenu}
            className="md:hidden p-2 rounded-lg hover:bg-muted transition-colors"
            aria-label="Toggle mobile menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isMobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t border-border/50 bg-background/95 backdrop-blur-sm">
            <div className="px-4 py-4 space-y-4">
              <a 
                href="#features" 
                className="block text-muted-foreground hover:text-foreground transition-colors duration-200 py-2"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Features
              </a>
              <a 
                href="#about" 
                className="block text-muted-foreground hover:text-foreground transition-colors duration-200 py-2"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                About
              </a>
              <a 
                href="#contact" 
                className="block text-muted-foreground hover:text-foreground transition-colors duration-200 py-2"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Contact
              </a>
              <div className="pt-4">
                {!isAuthenticated() ? (
                  <Button 
                    onClick={handleLogin}
                    disabled={loading}
                    className="btn-primary w-full"
                    size="sm"
                  >
                    {loading ? "Signing in..." : "Login with UNC"}
                  </Button>
                ) : (
                  <Button 
                    onClick={() => window.location.href = '/dashboard'}
                    className="btn-primary w-full"
                    size="sm"
                  >
                    Go to Dashboard
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
