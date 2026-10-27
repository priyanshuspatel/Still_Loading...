import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowRight,
  Play,
  Pause,
  Volume2,
  Eye,
} from 'lucide-react';
import { LEDMatrix } from './LEDMatrix';
import { HardwareLightState } from '../types/telemetry';
import { audioCues } from '../lib/audioCues';

interface HeroSectionProps {
  onOpenDashboard: () => void;
  onSeeHowItWorks: () => void;
  isLiveMode: boolean;
}

interface HeroScenario {
  id: string;
  code: number;
  label: string;
  caption: string;
  state: HardwareLightState;
  progress: number;
  waveColor: string;
  terminalLine: string;
  wireSummary: string;
}

const HERO_SCENARIOS: HeroScenario[] = [
  {
    id: 'download',
    code: 9,
    label: 'Chrome 68%',
    caption: 'Active .crdownload stream takes automatic foreground priority.',
    state: 'download',
    progress: 68,
    waveColor: '#0055FF',
    terminalLine: 'GET apple_event_october_4k.mp4.crdownload (84.9 / 124.7 MB)',
    wireSummary: 'POST /v1/download {"state":"downloading","progress":68}',
  },
  {
    id: 'charging',
    code: 7,
    label: 'MagSafe 46%',
    caption: 'Live MacBook charge percentage with animated bottom scanline.',
    state: 'battery_charging',
    progress: 46,
    waveColor: '#059669',
    terminalLine: "pmset -g batt → 'AC Power' (InternalBattery-0 46%; charging)",
    wireSummary: 'POST /v1/battery {"percent":46,"charging_state":"charging"}',
  },
  {
    id: 'running',
    code: 1,
    label: 'CLI Build 38%',
    caption: 'Subprocess wrapper emitting heartbeats every 2.0 seconds.',
    state: 'running',
    progress: 38,
    waveColor: '#0284C7',
    terminalLine: '$ python3 run_job.py --send -- cargo build --release (38%)',
    wireSummary: 'POST /v1/events {"event":"progress","sequence":18,"progress":38}',
  },
  {
    id: 'stall',
    code: 3,
    label: 'Stall [ ! ]',
    caption: '6.0s without a heartbeat triggers [ ! ] warning—never a false failure.',
    state: 'suspected_stall',
    progress: 42,
    waveColor: '#D97706',
    terminalLine: '[watchdog] 6.2s elapsed since sequence #22 — holding 42%',
    wireSummary: 'StateEngine clock > 6.0s → state="suspected_stall" (Code 03)',
  },
  {
    id: 'failed',
    code: 4,
    label: 'Failed (X)',
    caption: 'Redacted stderr excerpt + instant zero-overhead root cause fix.',
    state: 'failed',
    progress: 24,
    waveColor: '#DC2626',
    terminalLine: "ModuleNotFoundError: No module named 'pandas' (Exit 1)",
    wireSummary: 'POST /v1/events {"event":"failed","exit_code":1,"excerpt":"..."}',
  },
  {
    id: 'completed',
    code: 5,
    label: '100% Done',
    caption: '3× celebratory heart blink → compact 100 bar → steady checkmark.',
    state: 'completed',
    progress: 100,
    waveColor: '#10B981',
    terminalLine: 'Build finished in 18.4s (exit code 0) — 178/178 tests passing',
    wireSummary: 'POST /v1/events {"event":"completed","progress":100,"exit_code":0}',
  },
];

export const HeroSection: React.FC<HeroSectionProps> = ({
  onOpenDashboard,
  onSeeHowItWorks,
}) => {
  const [heroState, setHeroState] = useState<HardwareLightState>('download');
  const [heroProgress, setHeroProgress] = useState<number>(68);
  const [autoCycle, setAutoCycle] = useState<boolean>(false);
  const [glanceDistance, setGlanceDistance] = useState<'desk' | 'room'>('desk');
  const [chimeFeedback, setChimeFeedback] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const activeScenario =
    HERO_SCENARIOS.find((s) => s.state === heroState) || HERO_SCENARIOS[0];

  // 60fps Harmonic Telemetry Waveform Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let phase = 0;

    const renderWave = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const speed =
        heroState === 'failed'
          ? 0.015
          : heroState === 'suspected_stall'
          ? 0.03
          : 0.065;
      phase += speed;

      const amplitude =
        heroState === 'failed'
          ? 3
          : heroState === 'completed'
          ? 9
          : 7 + (heroProgress / 100) * 6;

      [1, 0.45].forEach((alpha, idx) => {
        ctx.beginPath();
        ctx.strokeStyle = activeScenario.waveColor;
        ctx.globalAlpha = alpha * 0.5;
        ctx.lineWidth = idx === 0 ? 1.75 : 1.1;

        for (let x = 0; x <= width; x += 4) {
          const freq = idx === 0 ? 0.02 : 0.03;
          const y =
            height / 2 +
            Math.sin(x * freq + phase + idx * 1.3) *
              amplitude *
              Math.sin((x / width) * Math.PI);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      });

      ctx.globalAlpha = 1;
      animId = requestAnimationFrame(renderWave);
    };

    animId = requestAnimationFrame(renderWave);
    return () => cancelAnimationFrame(animId);
  }, [heroState, heroProgress, activeScenario.waveColor]);

  // Live sequence simulation
  useEffect(() => {
    if (!autoCycle) return;
    const timer = setInterval(() => {
      setHeroProgress((prev) => {
        if (prev >= 100) {
          setHeroState('completed');
          setAutoCycle(false);
          return 100;
        }
        const next = Math.min(100, prev + 4);
        if (next === 44) {
          setHeroState('suspected_stall');
        } else if (next >= 52 && next < 100) {
          setHeroState('running');
        }
        return next;
      });
    }, 360);
    return () => clearInterval(timer);
  }, [autoCycle]);

  const handleSelectScenario = (scenario: HeroScenario) => {
    setAutoCycle(false);
    setHeroState(scenario.state);
    setHeroProgress(scenario.progress);
  };

  const handleToggleWalkthrough = () => {
    if (autoCycle) {
      setAutoCycle(false);
    } else {
      if (heroProgress >= 100) setHeroProgress(12);
      setHeroState('running');
      setAutoCycle(true);
    }
  };

  const triggerSynthPreview = (
    cue: 'completed' | 'stall' | 'failed',
    label: string
  ) => {
    audioCues.enable();
    audioCues.playCue(cue);
    setChimeFeedback(label);
    setTimeout(() => setChimeFeedback(null), 1800);
  };

  return (
    <section className="relative pt-20 pb-14 sm:pt-28 sm:pb-20 bg-[#F9F9F8] dark:bg-[#0C0D0F] border-b border-black/[0.08] dark:border-white/[0.08]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        {/* Top Split Header: Left Headline + Right Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-end">
          <div className="lg:col-span-8 space-y-3">
            <div className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#4A4D52] dark:text-[#9CA3AF]">
              <span className="w-2 h-2 rounded-full bg-[#0055FF] dark:bg-[#38BDF8]" />
              <span>Arduino UNO Q • 104 Optical LEDs • macOS Telemetry</span>
            </div>

            <h1 className="text-3xl sm:text-5xl lg:text-[56px] font-extrabold tracking-[-0.038em] text-[#141517] dark:text-white leading-[1.05]">
              Stop staring at screens.{' '}
              <span className="font-serif italic font-normal text-[#4A4D52] dark:text-[#9CA3AF]">
                Give waiting a physical form.
              </span>
            </h1>
          </div>

          <div className="lg:col-span-4 flex flex-col justify-end space-y-4">
            <p className="text-sm sm:text-base text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
              Translates MacBook battery charge, Chrome downloads, and terminal builds into calm peripheral light across your studio.
            </p>
            <div className="flex flex-wrap items-center gap-2.5">
              <button
                onClick={onOpenDashboard}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-xs sm:text-sm bg-[#141517] hover:bg-[#0055FF] dark:bg-white dark:hover:bg-[#38BDF8] text-white dark:text-[#141517] transition-colors"
              >
                <span>Open Control Deck</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={onSeeHowItWorks}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-xs sm:text-sm text-[#141517] dark:text-white bg-[#F1F0EC] hover:bg-[#E5E3DC] dark:bg-white/[0.07] dark:hover:bg-white/10 transition-colors"
              >
                <span>Architecture</span>
              </button>
            </div>
          </div>
        </div>

        {/* Architectural Joined Studio Stage (1px hairline seams, zero bubbly cards) */}
        <div className="arch-grid grid grid-cols-1 lg:grid-cols-12">
          {/* Primary Hardware Twin Stage (First on all viewports, 7 cols on desktop) */}
          <div className="lg:col-span-7 arch-cell-stone p-5 sm:p-8 flex flex-col items-center justify-between gap-5">
            <div className="w-full flex items-center justify-between text-xs">
              <span className="font-mono uppercase tracking-wider text-[#4A4D52] dark:text-[#9CA3AF] font-semibold">
                Physical Matrix Twin (1:1 STM32U585)
              </span>
              <button
                onClick={handleToggleWalkthrough}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-colors ${
                  autoCycle
                    ? 'bg-amber-500 text-white'
                    : 'bg-white dark:bg-[#181B20] text-[#141517] dark:text-white border border-black/10 dark:border-white/10 hover:border-[#0055FF]'
                }`}
              >
                {autoCycle ? (
                  <>
                    <Pause className="w-3 h-3" />
                    <span>Pause Lifecycle</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 text-[#0055FF] dark:text-[#38BDF8]" />
                    <span>Play Lifecycle</span>
                  </>
                )}
              </button>
            </div>

            <LEDMatrix
              state={heroState}
              progress={heroProgress}
              progressKnown={true}
              size="hero"
              showLabels={true}
              showLed3={true}
              interactive={true}
              className="w-full max-w-md"
            />

            {/* Scenario Selector Strip directly beneath Hardware */}
            <div className="w-full grid grid-cols-3 sm:grid-cols-6 gap-1.5 pt-1">
              {HERO_SCENARIOS.map((scenario) => {
                const active = heroState === scenario.state;
                return (
                  <button
                    key={scenario.id}
                    onClick={() => handleSelectScenario(scenario)}
                    className={`py-2 px-2 rounded-lg text-[11px] font-semibold text-center truncate transition-all ${
                      active
                        ? 'bg-[#141517] dark:bg-white text-white dark:text-[#141517] shadow-sm'
                        : 'bg-white dark:bg-[#181B20] text-[#4A4D52] dark:text-[#9CA3AF] hover:text-[#141517] dark:hover:text-white border border-black/[0.06] dark:border-white/10'
                    }`}
                  >
                    {scenario.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Telemetry Inspector & Room Glance Comparator (5 cols on desktop) */}
          <div className="lg:col-span-5 arch-cell flex flex-col justify-between divide-y divide-black/[0.08] dark:divide-white/[0.08]">
            {/* Cell 1: Active State & Harmonic Signal Wave */}
            <div className="p-5 sm:p-6 space-y-3">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[#0055FF] dark:text-[#38BDF8] font-semibold">
                  CODE 0{activeScenario.code} // {heroState.toUpperCase()}
                </span>
                <span className="text-[#787C82]">60Hz millis()</span>
              </div>

              <div className="flex items-baseline justify-between">
                <h2 className="text-xl font-bold text-[#141517] dark:text-white">
                  {activeScenario.label}
                </h2>
                <span className="text-2xl font-extrabold font-mono text-[#141517] dark:text-white">
                  {heroProgress}%
                </span>
              </div>

              <p className="text-xs sm:text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                {activeScenario.caption}
              </p>

              <canvas
                ref={canvasRef}
                width={400}
                height={36}
                className="w-full h-9 rounded-lg bg-[#F1F0EC] dark:bg-[#131519]"
              />
            </div>

            {/* Cell 2: Room Glance Optical Distance Comparator */}
            <div className="p-5 sm:p-6 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-[#141517] dark:text-white flex items-center gap-1.5">
                  <Eye className="w-3.5 h-3.5 text-[#0055FF] dark:text-[#38BDF8]" />
                  <span>Optical Distance Test</span>
                </span>

                <div className="flex items-center bg-[#F1F0EC] dark:bg-white/[0.06] p-0.5 rounded-lg text-[11px] font-semibold">
                  <button
                    onClick={() => setGlanceDistance('desk')}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      glanceDistance === 'desk'
                        ? 'bg-white dark:bg-[#252830] text-[#141517] dark:text-white shadow-sm'
                        : 'text-[#787C82]'
                    }`}
                  >
                    0.5m Desk
                  </button>
                  <button
                    onClick={() => setGlanceDistance('room')}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      glanceDistance === 'room'
                        ? 'bg-[#0055FF] text-white'
                        : 'text-[#787C82]'
                    }`}
                  >
                    3.0m Room
                  </button>
                </div>
              </div>

              <div
                className={`p-3.5 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] border border-black/[0.06] dark:border-white/[0.06] font-mono text-[11px] space-y-1 transition-all duration-500 ${
                  glanceDistance === 'room'
                    ? 'blur-[3px] opacity-45 select-none'
                    : 'blur-0 opacity-100'
                }`}
              >
                <div className="text-[#787C82] flex justify-between">
                  <span>macOS Terminal Window</span>
                  <span>{glanceDistance === 'room' ? 'Unreadable at 3m' : '0.5m'}</span>
                </div>
                <div className="text-[#141517] dark:text-white font-medium truncate">
                  {activeScenario.terminalLine}
                </div>
                <div className="text-[#787C82] truncate">
                  {activeScenario.wireSummary}
                </div>
              </div>
            </div>

            {/* Cell 3: Progress Fader & Web Audio Chimes */}
            <div className="p-5 sm:p-6 space-y-4">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label
                    htmlFor="hero-progress-fader"
                    className="font-semibold text-[#4A4D52] dark:text-[#9CA3AF]"
                  >
                    Scrub Progress
                  </label>
                  <span className="font-mono font-bold text-[#141517] dark:text-white">
                    {heroProgress}%
                  </span>
                </div>
                <input
                  id="hero-progress-fader"
                  type="range"
                  min={0}
                  max={100}
                  value={heroProgress}
                  onChange={(e) => {
                    setAutoCycle(false);
                    setHeroProgress(Number(e.target.value));
                  }}
                  className="w-full studio-fader"
                />
              </div>

              <div className="flex items-center justify-between gap-1.5 pt-1">
                <span className="text-[11px] text-[#787C82] flex items-center gap-1">
                  <Volume2 className="w-3.5 h-3.5 text-[#0055FF] dark:text-[#38BDF8]" />
                  <span>{chimeFeedback || 'Audio Synth:'}</span>
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => {
                      setHeroState('completed');
                      setHeroProgress(100);
                      triggerSynthPreview('completed', 'Glass Chime');
                    }}
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[#F1F0EC] hover:bg-emerald-500/15 dark:bg-white/10 text-[#141517] dark:text-white transition-colors"
                  >
                    ♪ Glass
                  </button>
                  <button
                    onClick={() => {
                      setHeroState('suspected_stall');
                      triggerSynthPreview('stall', 'Tink × 2');
                    }}
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[#F1F0EC] hover:bg-amber-500/15 dark:bg-white/10 text-[#141517] dark:text-white transition-colors"
                  >
                    ♪ Tink
                  </button>
                  <button
                    onClick={() => {
                      setHeroState('failed');
                      triggerSynthPreview('failed', 'Basso Pulse');
                    }}
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[#F1F0EC] hover:bg-red-500/15 dark:bg-white/10 text-[#141517] dark:text-white transition-colors"
                  >
                    ♪ Basso
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
