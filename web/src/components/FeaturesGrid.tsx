import React, { useState, useEffect } from 'react';
import {
  Copy,
  Check,
  Eye,
  EyeOff,
  RotateCcw,
} from 'lucide-react';
import { LEDMatrix } from './LEDMatrix';
import { DisplayMode, HardwareLightState } from '../types/telemetry';

export const FeaturesGrid: React.FC = () => {
  // Interactive 13-Column Typography Scrubber
  const [typoPercent, setTypoPercent] = useState<number>(100);

  // Interactive 6.0s Watchdog Stall Clock Simulator
  const [heartbeatPaused, setHeartbeatPaused] = useState<boolean>(false);
  const [sinceHeartbeatSec, setSinceHeartbeatSec] = useState<number>(0.8);

  useEffect(() => {
    const interval = setInterval(() => {
      setSinceHeartbeatSec((prev) => {
        if (!heartbeatPaused) {
          return prev >= 1.9 ? 0.1 : Number((prev + 0.2).toFixed(1));
        }
        return Number(Math.min(9.9, prev + 0.2).toFixed(1));
      });
    }, 200);
    return () => clearInterval(interval);
  }, [heartbeatPaused]);

  const isStalled = sinceHeartbeatSec >= 6.0;

  // Interactive Priority Arbitrator
  const [arbMode, setArbMode] = useState<DisplayMode>('auto');
  const [arbDownloadActive, setArbDownloadActive] = useState<boolean>(true);
  const [arbJobState, setArbJobState] = useState<'none' | 'running' | 'failed'>('running');
  const [arbBatteryCharging, setArbBatteryCharging] = useState<boolean>(false);

  const resolveArbitratedState = (): {
    winner: string;
    state: HardwareLightState;
    progress: number;
    reason: string;
  } => {
    if (arbMode === 'battery') {
      return {
        winner: 'MacBook Battery (Pinned)',
        state: arbBatteryCharging ? 'battery_charging' : 'battery',
        progress: 82,
        reason: 'Battery mode pins the display to continuous desk charge telemetry.',
      };
    }
    if (arbMode === 'job') {
      if (arbJobState === 'failed') {
        return {
          winner: 'CLI Build Failure',
          state: 'failed',
          progress: 24,
          reason: 'Job mode isolates terminal builds and ignores battery or browser downloads.',
        };
      }
      if (arbJobState === 'running') {
        return {
          winner: 'Active CLI Build',
          state: 'running',
          progress: 54,
          reason: 'Job mode displays active subprocess progress and heartbeats.',
        };
      }
      return {
        winner: 'Idle Waiting Dots',
        state: 'idle',
        progress: 0,
        reason: 'No terminal job is active; the matrix steps gently.',
      };
    }
    if (arbJobState === 'failed') {
      return {
        winner: 'Failed CLI Job (Latched)',
        state: 'failed',
        progress: 24,
        reason: 'A failed build latches steady X and red LED 3 so background battery polls never hide an error.',
      };
    }
    if (arbDownloadActive) {
      return {
        winner: 'Chrome Download (Foreground)',
        state: 'download',
        progress: 74,
        reason: 'Active Chrome transfers automatically step to the front until complete.',
      };
    }
    if (arbJobState === 'running') {
      return {
        winner: 'Active CLI Build',
        state: 'running',
        progress: 54,
        reason: 'Running terminal builds take priority over passive desk battery updates.',
      };
    }
    return {
      winner: 'MacBook Desk Battery',
      state: arbBatteryCharging ? 'battery_charging' : 'battery',
      progress: 82,
      reason: 'When no build or download is active, the matrix rests on your MacBook battery.',
    };
  };

  const arbResult = resolveArbitratedState();

  // Secret Redaction & Failure Explainer
  const [showRawSecrets, setShowRawSecrets] = useState<boolean>(false);
  const [copiedCmd, setCopiedCmd] = useState<boolean>(false);

  const rawTerminalOutput = `$ python3 deploy_worker.py --env prod
Connecting with Authorization: Bearer sk-live-98a7c4e2910f8b3a12
export OPENAI_API_KEY="sk-proj-secretKey998123"
Traceback (most recent call last):
  File "deploy_worker.py", line 14, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'`;

  const sanitizedExcerpt = `Connecting with Authorization: [REDACTED]
export OPENAI_API_KEY=[REDACTED]
Traceback (most recent call last):
  File "deploy_worker.py", line 14, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'`;

  const handleCopyCmd = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText('pip install pandas');
      setCopiedCmd(true);
      setTimeout(() => setCopiedCmd(false), 2000);
    }
  };

  return (
    <section className="py-16 sm:py-24 bg-[#F9F9F8] dark:bg-[#0C0D0F] border-b border-black/[0.08] dark:border-white/[0.08]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        {/* Section Editorial Heading */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-2 max-w-2xl">
            <div className="text-xs font-mono uppercase tracking-wider text-[#0055FF] dark:text-[#38BDF8] font-semibold">
              Engineering Specimens
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-[-0.035em] text-[#141517] dark:text-white leading-[1.06]">
              Every pixel has a reason.{' '}
              <span className="font-serif italic font-normal text-[#4A4D52] dark:text-[#9CA3AF]">
                Every timeout has grace.
              </span>
            </h2>
          </div>
          <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] max-w-md leading-relaxed">
            Designing for 104 LEDs means nothing can be accidental. Interact with the four core hardware subsystems below.
          </p>
        </div>

        {/* Joined Hairline Architectural Bento Grid */}
        <div className="arch-grid grid grid-cols-1 lg:grid-cols-12">
          {/* Specimen 01: 13-Column Optical Typography (7 cols) */}
          <div className="lg:col-span-7 arch-cell p-6 sm:p-8 flex flex-col justify-between space-y-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs font-mono text-[#787C82]">
                <span>01 // OPTICAL PIXEL TYPOGRAPHY</span>
                <span>3×5 GLYPHS + ROW 7 BAR</span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#141517] dark:text-white">
                How 100% fits on a 13-column canvas.
              </h3>
              <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                Three digits plus a percent sign would demand 15 columns. From <strong className="text-[#141517] dark:text-white">0% to 99%</strong>, Still Loading pairs proportional 3×5 numerals with a custom `%` glyph. At <strong className="text-[#141517] dark:text-white">100%</strong>, the `%` steps aside for a crisp three-digit <code className="px-1.5 py-0.5 rounded bg-[#F1F0EC] dark:bg-white/10 text-xs">100</code> underscored by a full 13-LED horizon bar.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-12 gap-5 items-center">
              <div className="sm:col-span-7 flex justify-center">
                <LEDMatrix
                  state="battery"
                  progress={typoPercent}
                  progressKnown={true}
                  size="md"
                  showLabels={false}
                  showLed3={false}
                />
              </div>

              <div className="sm:col-span-5 space-y-3">
                <div className="p-3.5 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] space-y-1">
                  <div className="text-[10px] font-mono uppercase text-[#787C82]">
                    Active Geometry
                  </div>
                  <div className="text-sm font-bold text-[#141517] dark:text-white">
                    {typoPercent === 100
                      ? 'Compact "100" + Full Bar'
                      : typoPercent < 10
                      ? `Single Digit "${typoPercent}" + %`
                      : `Dual Digits "${typoPercent}" + %`}
                  </div>
                  <div className="text-xs text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                    {typoPercent === 100
                      ? 'Cols 1–11 render "100"; all 13 LEDs on Row 7 illuminate.'
                      : typoPercent < 10
                      ? 'Centered across 9 columns with proportional Row 7 progress.'
                      : 'Cols 0–6 hold numerals; cols 8–12 form the % glyph.'}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-1.5">
                  {[7, 46, 88, 100].map((val) => (
                    <button
                      key={val}
                      onClick={() => setTypoPercent(val)}
                      className={`py-1.5 rounded-md text-xs font-mono font-semibold transition-all ${
                        typoPercent === val
                          ? 'bg-[#141517] dark:bg-white text-white dark:text-[#141517]'
                          : 'bg-[#F1F0EC] dark:bg-white/10 text-[#4A4D52] dark:text-[#9CA3AF]'
                      }`}
                    >
                      {val}%
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-black/[0.07] dark:border-white/[0.08] flex items-center gap-4">
              <span className="text-xs font-mono text-[#787C82] shrink-0">
                SCRUB 0–100%:
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={typoPercent}
                onChange={(e) => setTypoPercent(Number(e.target.value))}
                aria-label="Test percentage typography from 0 to 100 percent"
                className="w-full studio-fader"
              />
              <span className="text-xs font-mono font-bold text-[#141517] dark:text-white w-10 text-right">
                {typoPercent}%
              </span>
            </div>
          </div>

          {/* Specimen 02: The 6.0-Second Grace Period (5 cols) */}
          <div className="lg:col-span-5 arch-cell-stone p-6 sm:p-8 flex flex-col justify-between space-y-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[#787C82]">02 // HONEST TIMEKEEPING</span>
                <span
                  className={`px-2 py-0.5 rounded font-bold ${
                    isStalled
                      ? 'bg-amber-500/20 text-amber-800 dark:text-amber-300'
                      : 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300'
                  }`}
                >
                  {isStalled ? 'STALL [ ! ]' : 'HEARTBEAT OK'}
                </span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#141517] dark:text-white">
                Silence is a stall, not a crash.
              </h3>
              <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                If a compiler pauses for <strong>6.0 seconds</strong> without a heartbeat, the receiver’s independent clock shifts to a framed <code className="px-1.5 py-0.5 rounded bg-white dark:bg-white/10 text-xs">[ ! ]</code> alert—recovering the instant the next heartbeat arrives.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-[#181B20] border border-black/[0.07] dark:border-white/10 space-y-4">
              <div className="flex items-center justify-between gap-4">
                <LEDMatrix
                  state={isStalled ? 'suspected_stall' : 'running'}
                  progress={42}
                  progressKnown={true}
                  size="sm"
                  showLabels={false}
                  showLed3={false}
                />

                <div className="flex-1 space-y-2">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs font-mono text-[#787C82]">Watchdog</span>
                    <span
                      className={`text-xl font-bold font-mono ${
                        isStalled
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-[#141517] dark:text-white'
                      }`}
                    >
                      {sinceHeartbeatSec.toFixed(1)}s{' '}
                      <span className="text-xs font-normal text-[#787C82]">
                        / 6.0s
                      </span>
                    </span>
                  </div>

                  <div className="w-full h-2 rounded-sm bg-black/[0.08] dark:bg-white/10 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-200 ${
                        isStalled ? 'bg-amber-500' : 'bg-[#0055FF] dark:bg-[#38BDF8]'
                      }`}
                      style={{
                        width: `${Math.min(100, (sinceHeartbeatSec / 6.0) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs font-semibold">
                <button
                  onClick={() => {
                    setHeartbeatPaused(true);
                    if (sinceHeartbeatSec < 4.5) setSinceHeartbeatSec(4.8);
                  }}
                  className={`py-2 px-3 rounded-lg transition-all ${
                    heartbeatPaused
                      ? 'bg-amber-500 text-white'
                      : 'bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white'
                  }`}
                >
                  Simulate Hang
                </button>

                <button
                  onClick={() => {
                    setHeartbeatPaused(false);
                    setSinceHeartbeatSec(0.0);
                  }}
                  className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-[#141517] dark:bg-white text-white dark:text-[#141517] transition-all"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Send Heartbeat</span>
                </button>
              </div>
            </div>
          </div>

          {/* Specimen 03: Priority Arbitrator (5 cols) */}
          <div className="lg:col-span-5 arch-cell-stone p-6 sm:p-8 flex flex-col justify-between space-y-5">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs font-mono text-[#787C82]">
                <span>03 // PRIORITY ARBITRATION</span>
                <span>AUTO • JOB • BATTERY</span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#141517] dark:text-white">
                Foreground work wins automatically.
              </h3>
              <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                Toggle simultaneous Mac signals below to verify how the state engine ensures a background battery update never masks an active download or crash.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center bg-white dark:bg-[#181B20] p-1 rounded-lg border border-black/[0.07] dark:border-white/10 font-semibold">
                {(['auto', 'job', 'battery'] as DisplayMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setArbMode(m)}
                    className={`flex-1 py-1.5 rounded-md capitalize transition-all ${
                      arbMode === m
                        ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517]'
                        : 'text-[#787C82]'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setArbDownloadActive(!arbDownloadActive)}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    arbDownloadActive
                      ? 'bg-white dark:bg-[#181B20] border-[#0055FF] text-[#141517] dark:text-white'
                      : 'bg-white/60 dark:bg-[#181B20]/50 border-black/[0.06] text-[#787C82]'
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase">Chrome Download</div>
                  <div className="font-bold mt-0.5">
                    {arbDownloadActive ? '● Active (74%)' : '○ Idle'}
                  </div>
                </button>

                <button
                  onClick={() =>
                    setArbJobState((prev) =>
                      prev === 'running'
                        ? 'failed'
                        : prev === 'failed'
                        ? 'none'
                        : 'running'
                    )
                  }
                  className={`p-3 rounded-lg border text-left transition-all ${
                    arbJobState === 'failed'
                      ? 'bg-red-500/10 border-red-500/40 text-red-900 dark:text-red-200'
                      : arbJobState === 'running'
                      ? 'bg-white dark:bg-[#181B20] border-[#0055FF] text-[#141517] dark:text-white'
                      : 'bg-white/60 dark:bg-[#181B20]/50 border-black/[0.06] text-[#787C82]'
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase">Terminal Build</div>
                  <div className="font-bold mt-0.5 capitalize">
                    {arbJobState === 'none' ? '○ Idle' : `● ${arbJobState}`}
                  </div>
                </button>
              </div>

              <div className="p-3.5 rounded-lg bg-[#141517] text-white space-y-1">
                <div className="flex items-center justify-between text-[10px] font-mono text-[#38BDF8] uppercase">
                  <span>Winning Matrix Display</span>
                  <button
                    onClick={() => setArbBatteryCharging(!arbBatteryCharging)}
                    className="underline text-slate-300 hover:text-white"
                  >
                    Battery: {arbBatteryCharging ? 'Charging' : '82%'}
                  </button>
                </div>
                <div className="text-sm font-bold">{arbResult.winner}</div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {arbResult.reason}
                </p>
              </div>
            </div>
          </div>

          {/* Specimen 04: Secret Redaction & Failure Intelligence (7 cols) */}
          <div className="lg:col-span-7 arch-cell p-6 sm:p-8 flex flex-col justify-between space-y-5">
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-[#787C82]">
                <span>04 // FAILURE INTELLIGENCE & REDACTION</span>
                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                  MAX 512B • SECRETS STRIPPED
                </span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#141517] dark:text-white">
                Articulate when builds fail. Silent about your secrets.
              </h3>
              <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
                When a process exits non-zero, Still Loading captures the last 10 lines, scrubs <code className="px-1.5 py-0.5 rounded bg-[#F1F0EC] dark:bg-white/10 text-xs">Bearer</code> tokens and API keys before they leave your Mac, and diagnoses the root cause in under a millisecond.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-stretch">
              <div className="md:col-span-7 flex flex-col">
                <div className="flex items-center justify-between mb-1.5 text-xs">
                  <span className="font-mono text-[#787C82]">
                    {showRawSecrets ? 'Unredacted Local Stderr' : 'Sanitized Wire Excerpt'}
                  </span>
                  <button
                    onClick={() => setShowRawSecrets(!showRawSecrets)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white text-[11px] font-semibold"
                  >
                    {showRawSecrets ? (
                      <>
                        <EyeOff className="w-3 h-3 text-emerald-600" />
                        <span>Redact Secrets</span>
                      </>
                    ) : (
                      <>
                        <Eye className="w-3 h-3 text-amber-600" />
                        <span>Peek Raw Log</span>
                      </>
                    )}
                  </button>
                </div>

                <pre className="flex-1 p-3.5 rounded-lg bg-[#141517] text-slate-200 font-mono text-[11px] leading-relaxed overflow-x-auto">
                  {showRawSecrets ? rawTerminalOutput : sanitizedExcerpt}
                </pre>
              </div>

              <div className="md:col-span-5 flex flex-col justify-between p-4 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] space-y-3">
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] font-mono uppercase text-red-600 dark:text-red-400 font-bold">
                    <span>Root Cause</span>
                    <span>Exit 1</span>
                  </div>
                  <p className="text-sm font-bold text-[#141517] dark:text-white">
                    Missing Python module: &apos;pandas&apos;
                  </p>
                  <p className="text-xs text-[#4A4D52] dark:text-[#9CA3AF]">
                    Classified locally via rules-first engine with zero cloud LLM calls.
                  </p>
                </div>

                <div className="space-y-1.5 pt-2.5 border-t border-black/[0.08] dark:border-white/10">
                  <div className="text-[10px] font-mono uppercase text-[#787C82]">
                    Suggested Fix
                  </div>
                  <div className="flex items-center justify-between gap-2 p-2 rounded-md bg-white dark:bg-[#181B20] border border-black/[0.07] dark:border-white/10 font-mono text-xs">
                    <code className="text-[#141517] dark:text-white font-semibold">
                      pip install pandas
                    </code>
                    <button
                      onClick={handleCopyCmd}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#141517] hover:bg-[#0055FF] text-white text-[11px] font-sans font-semibold transition-colors"
                    >
                      {copiedCmd ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
