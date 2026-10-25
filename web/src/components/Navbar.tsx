import React, { useState, useEffect } from 'react';
import { Radio, Menu, X, Terminal, Cpu } from 'lucide-react';

interface NavbarProps {
  currentTab: 'home' | 'dashboard' | 'architecture' | 'about';
  setCurrentTab: (tab: 'home' | 'dashboard' | 'architecture' | 'about') => void;
  isLiveMode: boolean;
  setIsLiveMode: (live: boolean) => void;
  isStale?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  setCurrentTab,
  isLiveMode,
  setIsLiveMode,
  isStale = false,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navItems = [
    { id: 'home', label: 'Home' },
    { id: 'dashboard', label: 'Live Dashboard' },
    { id: 'architecture', label: 'How It Works' },
    { id: 'about', label: 'About' },
  ] as const;

  const handleNavClick = (tab: 'home' | 'dashboard' | 'architecture' | 'about') => {
    setCurrentTab(tab);
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-graphite-950/85 backdrop-blur-md border-b border-white/[0.08] shadow-lg shadow-black/40 py-3'
          : 'bg-graphite-950/40 backdrop-blur-sm border-b border-white/[0.04] py-4'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Brand Wordmark */}
          <button
            onClick={() => handleNavClick('home')}
            className="flex items-center gap-3 text-left group focus:outline-none focus-visible:ring-2 focus-visible:ring-led-blue/60 rounded-lg p-1"
          >
            <div className="w-8 h-8 rounded-lg bg-graphite-900 border border-white/10 flex items-center justify-center shadow-inner group-hover:border-led-blue/50 transition-colors">
              <div className="flex items-center gap-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-led-blue animate-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-led-blue/70" />
                <span className="w-1.5 h-1.5 rounded-full bg-led-blue/40" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold tracking-tight text-white group-hover:text-led-blue transition-colors text-base sm:text-lg">
                  Still Loading<span className="text-led-blue">...</span>
                </span>
                <span className="hidden sm:inline-block px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider rounded border border-white/10 bg-white/5 text-graphite-400">
                  8×13 LED
                </span>
              </div>
              <span className="hidden md:block text-[11px] text-graphite-400 font-mono">
                stillloading.tech
              </span>
            </div>
          </button>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1 bg-graphite-900/60 border border-white/[0.06] rounded-full p-1 shadow-inner">
            {navItems.map((item) => {
              const active = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-led-blue ${
                    active
                      ? 'bg-graphite-800 text-white shadow-sm border border-white/10'
                      : 'text-graphite-400 hover:text-graphite-200 hover:bg-white/[0.02]'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right Controls: Mode Indicator & CTA */}
          <div className="hidden sm:flex items-center gap-3">
            {/* Mode Switcher Toggle */}
            <div className="flex items-center bg-graphite-900 border border-white/10 rounded-full p-1 text-xs font-mono">
              <button
                onClick={() => setIsLiveMode(false)}
                className={`px-3 py-1 rounded-full transition-all ${
                  !isLiveMode
                    ? 'bg-accent-lime/20 text-accent-lime font-semibold border border-accent-lime/30 shadow-[0_0_8px_rgba(190,242,100,0.2)]'
                    : 'text-graphite-400 hover:text-white'
                }`}
                title="Use realistic simulated hardware telemetry"
              >
                DEMO
              </button>
              <button
                onClick={() => setIsLiveMode(true)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full transition-all ${
                  isLiveMode
                    ? isStale
                      ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40'
                      : 'bg-led-blue/20 text-led-blue font-semibold border border-led-blue/40 shadow-[0_0_8px_rgba(56,189,248,0.25)]'
                    : 'text-graphite-400 hover:text-white'
                }`}
                title="Connect to live hardware telemetry endpoint"
              >
                <Radio className={`w-3 h-3 ${isLiveMode && !isStale ? 'animate-pulse' : ''}`} />
                LIVE
              </button>
            </div>

            {/* Direct Dashboard CTA */}
            <button
              onClick={() => handleNavClick('dashboard')}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-led-blue to-sky-400 text-graphite-950 font-semibold hover:shadow-led-glow hover:brightness-105 active:scale-95 transition-all"
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>Open Dashboard</span>
            </button>
          </div>

          {/* Mobile Menu Trigger */}
          <div className="flex items-center gap-2 md:hidden">
            <button
              onClick={() => setIsLiveMode(!isLiveMode)}
              className={`px-2.5 py-1 rounded-full text-[10px] font-mono uppercase font-semibold border ${
                isLiveMode
                  ? 'bg-led-blue/20 text-led-blue border-led-blue/40'
                  : 'bg-accent-lime/20 text-accent-lime border-accent-lime/40'
              }`}
            >
              {isLiveMode ? 'LIVE' : 'DEMO'}
            </button>

            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg bg-graphite-900 border border-white/10 text-graphite-300 hover:text-white focus:outline-none focus:ring-2 focus:ring-led-blue"
              aria-label={mobileMenuOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-white/10 bg-graphite-950/95 backdrop-blur-xl px-4 pt-3 pb-6 space-y-2 animate-in slide-in-from-top-4 duration-200">
          <div className="flex flex-col space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`flex items-center justify-between w-full px-4 py-2.5 rounded-lg text-sm text-left font-medium transition-colors ${
                  currentTab === item.id
                    ? 'bg-graphite-800 text-white border border-white/10'
                    : 'text-graphite-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <span>{item.label}</span>
                {currentTab === item.id && (
                  <span className="w-1.5 h-1.5 rounded-full bg-led-blue" />
                )}
              </button>
            ))}
          </div>

          <div className="pt-3 border-t border-white/10 flex flex-col gap-2">
            <div className="flex items-center justify-between px-2 text-xs font-mono text-graphite-400">
              <span>Telemetry Mode</span>
              <div className="flex items-center gap-1 bg-graphite-900 p-0.5 rounded-full border border-white/10">
                <button
                  onClick={() => setIsLiveMode(false)}
                  className={`px-2.5 py-0.5 rounded-full text-[10px] ${
                    !isLiveMode ? 'bg-accent-lime text-black font-bold' : 'text-graphite-400'
                  }`}
                >
                  DEMO
                </button>
                <button
                  onClick={() => setIsLiveMode(true)}
                  className={`px-2.5 py-0.5 rounded-full text-[10px] ${
                    isLiveMode ? 'bg-led-blue text-black font-bold' : 'text-graphite-400'
                  }`}
                >
                  LIVE
                </button>
              </div>
            </div>

            <button
              onClick={() => handleNavClick('dashboard')}
              className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold bg-led-blue text-graphite-950 hover:brightness-105"
            >
              <Terminal className="w-4 h-4" />
              <span>Explore Live Dashboard</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
};
