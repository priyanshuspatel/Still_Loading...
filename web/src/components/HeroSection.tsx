import React, { useState } from 'react';
import { ArrowRight, Layers, Sparkles, CheckCircle2, BatteryCharging, DownloadCloud } from 'lucide-react';
import { LEDMatrix } from './LEDMatrix';
import { HardwareLightState } from '../types/telemetry';

interface HeroSectionProps {
  onOpenDashboard: () => void;
  onSeeHowItWorks: () => void;
  isLiveMode: boolean;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onOpenDashboard,
  onSeeHowItWorks,
  isLiveMode,
}) => {
  // Hero interactive state preview selector
  const [heroState, setHeroState] = useState<HardwareLightState>('download');
  const [heroProgress, setHeroProgress] = useState(68);

  const heroPresets: {
    label: string;
    state: HardwareLightState;
    progress: number;
    icon: React.ReactNode;
  }[] = [
    {
      label: 'Chrome Download 68%',
      state: 'download',
      progress: 68,
      icon: <DownloadCloud className="w-3.5 h-3.5" />,
    },
    {
      label: 'MagSafe Charge 46%',
      state: 'battery_charging',
      progress: 46,
      icon: <BatteryCharging className="w-3.5 h-3.5" />,
    },
    {
      label: 'Desk Battery 82%',
      state: 'battery',
      progress: 82,
      icon: <Sparkles className="w-3.5 h-3.5" />,
    },
    {
      label: 'Stall Alert [ ! ]',
      state: 'suspected_stall',
      progress: 42,
      icon: <Layers className="w-3.5 h-3.5" />,
    },
    {
      label: '100% Complete',
      state: 'completed',
      progress: 100,
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    },
  ];

  const handleSelectPreset = (state: HardwareLightState, progress: number) => {
    setHeroState(state);
    setHeroProgress(progress);
  };

  return (
    <section className="relative pt-28 pb-20 sm:pt-36 sm:pb-28 overflow-hidden">
      {/* Background Subtle Ambient Gradients */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-gradient-to-tr from-led-blue/10 via-sky-600/5 to-transparent rounded-full blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-1/3 right-10 w-[400px] h-[300px] bg-accent-lime/5 rounded-full blur-3xl pointer-events-none -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Editorial Product Narrative */}
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            {/* Project Pill */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-graphite-900 border border-white/10 text-xs font-mono text-graphite-300 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-accent-lime animate-pulse" />
              <span className="text-white font-medium">Physical Telemetry</span>
              <span className="text-graphite-600">•</span>
              <span className="text-graphite-400">Arduino UNO Q & macOS</span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.12]">
              Waiting deserves a{' '}
              <span className="bg-gradient-to-r from-led-blue via-sky-300 to-accent-lime bg-clip-text text-transparent">
                better display.
              </span>
            </h1>

            {/* Supporting Copy */}
            <p className="text-lg sm:text-xl text-graphite-300 max-w-2xl mx-auto lg:mx-0 font-normal leading-relaxed">
              Still Loading... turns your MacBook’s battery state and Chrome download progress into real-world physical light.
              Stop staring at screen percentages. Now your waiting has an instrument.
            </p>

            {/* Brand Statement Callout */}
            <div className="p-4 rounded-xl bg-graphite-900/60 border border-white/[0.06] backdrop-blur-sm max-w-xl mx-auto lg:mx-0 text-left">
              <div className="text-xs font-mono text-graphite-400 uppercase tracking-wider mb-1">
                Core Philosophy
              </div>
              <p className="text-sm font-medium text-graphite-200">
                “Progress you can feel, not just watch. Your Mac does the heavy waiting — now the waiting has a dedicated desk display.”
              </p>
            </div>

            {/* Actions */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
              <button
                onClick={onOpenDashboard}
                className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl font-semibold text-sm bg-led-blue text-graphite-950 hover:bg-sky-300 shadow-led-glow hover:shadow-[0_0_25px_rgba(56,189,248,0.7)] active:scale-[0.98] transition-all"
              >
                <span>Open Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={onSeeHowItWorks}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl font-medium text-sm text-graphite-200 bg-graphite-900/80 hover:bg-graphite-800 border border-white/10 hover:border-white/20 transition-all"
              >
                <Layers className="w-4 h-4 text-graphite-400" />
                <span>See How It Works</span>
              </button>
            </div>

            {/* Real Hardware Spec Badges */}
            <div className="pt-4 flex flex-wrap items-center justify-center lg:justify-start gap-3 text-xs font-mono text-graphite-400">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-graphite-900/90 border border-white/5">
                <span className="w-1.5 h-1.5 rounded-full bg-led-blue" />
                8×13 Blue Matrix (104 LEDs)
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-graphite-900/90 border border-white/5">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-lime" />
                Active RGB LED 3
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-graphite-900/90 border border-white/5">
                Qualcomm QRB2210 + STM32U585
              </span>
            </div>
          </div>

          {/* Right Column: Hero Physical LED Matrix Instrument */}
          <div className="lg:col-span-5 flex flex-col items-center">
            <div className="relative w-full max-w-md mx-auto">
              {/* Outer Decorative Ring */}
              <div className="absolute -inset-1.5 bg-gradient-to-b from-led-blue/20 via-white/5 to-transparent rounded-3xl blur-md -z-10" />

              {/* Real 8x13 Matrix Display */}
              <div className="w-full flex justify-center">
                <LEDMatrix
                  state={heroState}
                  progress={heroProgress}
                  progressKnown={true}
                  size="hero"
                  showLabels={true}
                  showLed3={true}
                  interactive={true}
                  className="w-full max-w-sm sm:max-w-md"
                />
              </div>

              {/* Mode Indicator & Preset Audition Controls */}
              <div className="mt-4 p-3 rounded-xl bg-graphite-900/90 border border-white/10 backdrop-blur-md shadow-panel space-y-2.5">
                <div className="flex items-center justify-between text-xs font-mono text-graphite-400 border-b border-white/[0.06] pb-2">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-accent-lime" />
                    <span>Audition Physical States:</span>
                  </span>
                  <span className="text-[10px] text-graphite-500">
                    {isLiveMode ? 'LIVE SYNC OFF' : 'INTERACTIVE PREVIEW'}
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {heroPresets.map((preset) => {
                    const active = heroState === preset.state;
                    return (
                      <button
                        key={preset.label}
                        onClick={() => handleSelectPreset(preset.state, preset.progress)}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all ${
                          active
                            ? 'bg-led-blue/20 text-led-blue border border-led-blue/40 font-medium'
                            : 'bg-graphite-800/80 text-graphite-400 hover:text-white hover:bg-graphite-800 border border-white/5'
                        }`}
                      >
                        {preset.icon}
                        <span>{preset.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
