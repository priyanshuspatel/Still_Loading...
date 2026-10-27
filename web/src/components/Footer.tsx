import React from 'react';
import { ArrowUp } from 'lucide-react';

interface FooterProps {
  onNavigate: (tab: 'home' | 'dashboard' | 'architecture' | 'about') => void;
  isLiveMode: boolean;
}

export const Footer: React.FC<FooterProps> = ({ onNavigate, isLiveMode }) => {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="bg-[#F9F9F8] dark:bg-[#0C0D0F] text-[#4A4D52] dark:text-[#9CA3AF] py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 pb-10 border-b border-black/[0.08] dark:border-white/10">
          <div className="md:col-span-5 space-y-2.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-[#141517] dark:bg-white/10 flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8]" />
              </div>
              <span className="text-sm font-bold text-[#141517] dark:text-white tracking-tight">
                Still Loading
              </span>
            </div>
            <p className="text-xs text-[#4A4D52] dark:text-[#9CA3AF] max-w-sm leading-relaxed">
              Progress you can feel, not just watch. Connecting macOS battery telemetry, Chrome downloads, and terminal builds to an Arduino UNO Q 8×13 physical LED matrix.
            </p>
          </div>

          <div className="md:col-span-3 space-y-2">
            <div className="text-xs font-mono uppercase tracking-wider text-[#141517] dark:text-white font-bold">
              Navigation
            </div>
            <ul className="space-y-1.5 text-xs">
              <li>
                <button
                  onClick={() => onNavigate('home')}
                  className="hover:text-[#0055FF] dark:hover:text-[#38BDF8] transition-colors"
                >
                  Overview
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('dashboard')}
                  className="hover:text-[#0055FF] dark:hover:text-[#38BDF8] transition-colors"
                >
                  Telemetry Control Deck
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('architecture')}
                  className="hover:text-[#0055FF] dark:hover:text-[#38BDF8] transition-colors"
                >
                  System Architecture
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('about')}
                  className="hover:text-[#0055FF] dark:hover:text-[#38BDF8] transition-colors"
                >
                  Design Philosophy
                </button>
              </li>
            </ul>
          </div>

          <div className="md:col-span-4 space-y-1.5">
            <div className="text-xs font-mono uppercase tracking-wider text-[#141517] dark:text-white font-bold">
              Hardware Summary
            </div>
            <ul className="space-y-1 text-xs font-mono text-[#787C82]">
              <li>Arduino UNO Q (QRB2210 Linux + STM32U585)</li>
              <li>8×13 Matrix: 104 Blue LEDs (3-bit grayscale)</li>
              <li>Companion RGB LED 3 (Active-Low PH10–PH12)</li>
              <li>178 Automated Unit & Integration Tests</li>
            </ul>
          </div>
        </div>

        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-xs font-mono text-[#787C82] gap-4">
          <div className="flex items-center gap-2.5">
            <span>© 2026 Still Loading (stillloading.tech)</span>
            <span>•</span>
            <span className="text-[#141517] dark:text-white font-semibold">
              {isLiveMode ? 'Live Hardware Mode' : 'Interactive Demo Mode'}
            </span>
          </div>

          <button
            onClick={scrollToTop}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F1F0EC] hover:bg-[#141517] hover:text-white dark:bg-white/10 text-[#141517] dark:text-white font-semibold transition-colors"
          >
            <span>Top</span>
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </footer>
  );
};
