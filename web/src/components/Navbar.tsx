import React, { useState, useEffect } from 'react';
import { Radio, Menu, X, ArrowUpRight, Sun, Moon } from 'lucide-react';
import { useTheme } from '../lib/theme';

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
  const { theme, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 8);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navItems = [
    { id: 'home', label: 'Overview' },
    { id: 'dashboard', label: 'Control Deck' },
    { id: 'architecture', label: 'Architecture' },
    { id: 'about', label: 'Philosophy' },
  ] as const;

  const handleNavClick = (tab: 'home' | 'dashboard' | 'architecture' | 'about') => {
    setCurrentTab(tab);
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        scrolled
          ? 'bg-[#F9F9F8]/92 dark:bg-[#0C0D0F]/92 backdrop-blur-xl border-b border-black/[0.08] dark:border-white/[0.08] py-2.5'
          : 'bg-[#F9F9F8]/80 dark:bg-[#0C0D0F]/80 backdrop-blur-md border-b border-black/[0.05] dark:border-white/[0.05] py-3'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-2">
          {/* Brand Wordmark */}
          <button
            onClick={() => handleNavClick('home')}
            className="flex items-center gap-2.5 text-left group focus:outline-none rounded-lg py-0.5 shrink-0"
          >
            <div className="w-7 h-7 rounded-lg bg-[#141517] dark:bg-white/10 flex items-center justify-center">
              <div className="flex items-center gap-[2.5px]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8]/70" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8]/35" />
              </div>
            </div>

            <span className="font-bold tracking-tight text-[#141517] dark:text-white text-[15px] sm:text-base">
              Still Loading
            </span>
          </button>

          {/* Center Navigation (md+ viewports so it never crowds narrow panes) */}
          <nav
            aria-label="Primary Navigation"
            className="hidden md:flex items-center bg-[#F1F0EC] dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] rounded-lg p-0.5"
          >
            {navItems.map((item) => {
              const active = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all duration-150 ${
                    active
                      ? 'bg-white dark:bg-[#252830] text-[#141517] dark:text-white shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
                      : 'text-[#4A4D52] dark:text-[#9CA3AF] hover:text-[#141517] dark:hover:text-white'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right Controls (md+ viewports) */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <div
              className="flex items-center bg-[#F1F0EC] dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] rounded-lg p-0.5 text-[11px] font-medium"
              role="group"
              aria-label="Telemetry source mode"
            >
              <button
                onClick={() => setIsLiveMode(false)}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  !isLiveMode
                    ? 'bg-white dark:bg-[#252830] text-[#141517] dark:text-white font-semibold shadow-sm'
                    : 'text-[#787C82] hover:text-[#141517] dark:hover:text-white'
                }`}
              >
                Demo
              </button>
              <button
                onClick={() => setIsLiveMode(true)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all ${
                  isLiveMode
                    ? isStale
                      ? 'bg-amber-500/15 text-amber-800 dark:text-amber-300 font-semibold'
                      : 'bg-[#0055FF] text-white font-semibold'
                    : 'text-[#787C82] hover:text-[#141517] dark:hover:text-white'
                }`}
              >
                <Radio className={`w-3 h-3 ${isLiveMode && !isStale ? 'animate-pulse' : ''}`} />
                <span>Live</span>
              </button>
            </div>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-[#F1F0EC] hover:bg-[#E5E3DC] dark:bg-white/[0.06] dark:hover:bg-white/10 text-[#141517] dark:text-white transition-colors"
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Studio`}
              aria-label="Toggle studio appearance"
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-[#4A4D52]" />
              )}
            </button>

            <button
              onClick={() => handleNavClick('dashboard')}
              className="flex items-center gap-1 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#141517] hover:bg-[#0055FF] dark:bg-white dark:hover:bg-[#38BDF8] text-white dark:text-[#141517] transition-colors"
            >
              <span>Control Deck</span>
              <ArrowUpRight className="w-3.5 h-3.5 opacity-80" />
            </button>
          </div>

          {/* Compact / Mobile Controls (<768px) */}
          <div className="flex items-center gap-1.5 md:hidden">
            <button
              onClick={() => handleNavClick(currentTab === 'dashboard' ? 'home' : 'dashboard')}
              className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-[#141517] dark:bg-white text-white dark:text-[#141517]"
            >
              {currentTab === 'dashboard' ? 'Overview' : 'Control Deck'}
            </button>

            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-[#4A4D52]" />
              )}
            </button>

            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded-lg bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white"
              aria-label={mobileMenuOpen ? 'Close Menu' : 'Open Menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Compact Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-black/[0.08] dark:border-white/10 bg-[#F9F9F8] dark:bg-[#0C0D0F] px-4 pt-2 pb-5 space-y-2.5 shadow-lg">
          <div className="grid grid-cols-2 gap-1.5">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs text-left font-semibold transition-colors ${
                  currentTab === item.id
                    ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517]'
                    : 'bg-[#F1F0EC] dark:bg-white/5 text-[#4A4D52] dark:text-[#9CA3AF]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          <div className="pt-2 border-t border-black/[0.06] dark:border-white/10 flex items-center justify-between gap-2">
            <button
              onClick={() => setIsLiveMode(!isLiveMode)}
              className="w-full py-2 px-3 rounded-lg text-xs font-semibold bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white"
            >
              Telemetry Mode: {isLiveMode ? 'Live Hardware' : 'Interactive Demo'}
            </button>
          </div>
        </div>
      )}
    </header>
  );
};
