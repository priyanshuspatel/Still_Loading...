import React from 'react';
import { ArrowUp, Radio } from 'lucide-react';

interface FooterProps {
  onNavigate: (tab: 'home' | 'dashboard' | 'architecture' | 'about') => void;
  isLiveMode: boolean;
}

export const Footer: React.FC<FooterProps> = ({ onNavigate, isLiveMode }) => {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="bg-graphite-950 border-t border-white/[0.08] text-graphite-400 py-14">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pb-12 border-b border-white/[0.06]">
          {/* Brand Col */}
          <div className="md:col-span-5 space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-graphite-900 border border-white/10 flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-led-blue" />
              </div>
              <span className="text-base font-bold text-white tracking-tight">
                Still Loading<span className="text-led-blue">...</span>
              </span>
            </div>
            <p className="text-sm text-graphite-400 max-w-sm leading-relaxed">
              Progress you can feel, not just watch. Connecting MacBook battery telemetry and Chrome download progress to an Arduino UNO Q 8×13 physical LED matrix.
            </p>
            <div className="text-xs font-mono text-graphite-500">
              Domain: <span className="text-graphite-300">stillloading.tech</span>
            </div>
          </div>

          {/* Links Col 1: Experience */}
          <div className="md:col-span-3 space-y-2">
            <div className="text-xs font-mono uppercase tracking-wider text-graphite-300 font-semibold mb-3">
              Experience
            </div>
            <ul className="space-y-2 text-sm">
              <li>
                <button
                  onClick={() => onNavigate('home')}
                  className="hover:text-white transition-colors"
                >
                  Home Overview
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('dashboard')}
                  className="hover:text-white transition-colors"
                >
                  Live Dashboard
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('architecture')}
                  className="hover:text-white transition-colors"
                >
                  Architecture & Flow
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('about')}
                  className="hover:text-white transition-colors"
                >
                  Project Philosophy
                </button>
              </li>
            </ul>
          </div>

          {/* Links Col 2: Architecture & Hardware */}
          <div className="md:col-span-4 space-y-2">
            <div className="text-xs font-mono uppercase tracking-wider text-graphite-300 font-semibold mb-3">
              Hardware Details
            </div>
            <ul className="space-y-2 text-xs font-mono text-graphite-400">
              <li>• Arduino UNO Q (QRB2210 + STM32U585)</li>
              <li>• 8×13 Matrix: 104 Blue LEDs (3-bit grayscale)</li>
              <li>• Local Port: 8090 (HTTP/1.0 Bearer Authenticated)</li>
              <li>• macOS Agent: pmset + Chrome Observers</li>
              <li>• Automated Tests: 74 Verified Unit Tests</li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs font-mono text-graphite-500 gap-4">
          <div className="flex items-center gap-3">
            <span>© 2026 Still Loading...</span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${isLiveMode ? 'bg-led-blue' : 'bg-accent-lime'}`} />
              <span>{isLiveMode ? 'Live Mode Active' : 'Demo Mode Active'}</span>
            </span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={scrollToTop}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-graphite-900 hover:bg-graphite-800 text-graphite-300 hover:text-white border border-white/5 transition-colors"
            >
              <span>Back to Top</span>
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
};
