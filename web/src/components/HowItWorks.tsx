import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  ChevronRight,
  Send,
  Copy,
  Check,
} from 'lucide-react';

export const HowItWorks: React.FC = () => {
  const [activeStep, setActiveStep] = useState<number>(0);
  const [packetAnimating, setPacketAnimating] = useState<boolean>(false);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);

  const steps = [
    {
      id: 0,
      stepLabel: '01',
      title: 'macOS System Observers',
      subtitle: 'pmset • Chrome .crdownload • Subprocess Runner',
      latency: '0.2 ms parse',
      shortDesc:
        'Standard-library Python observers on your Mac track battery state, Chrome transfers, and CLI builds.',
      details: [
        'battery_monitor.py reads pmset -g batt every 15s with automatic 5-minute refresh.',
        'download_monitor.py observes active Chrome .crdownload streams for real-time transfer progress.',
        'run_job.py wraps arbitrary CLI commands, emitting started, heartbeat, progress, failed, or completed.',
        'Every wire payload is validated locally against shared/message_schema.json before sending.',
      ],
      codeSnippet: `# Watch any terminal build & forward to UNO Q:
python3 mac-agent/run_job.py --send --config config.local.json \\
  -- cargo build --release

# Or start continuous desk battery telemetry:
python3 mac-agent/battery_monitor.py --mode auto --config config.local.json`,
    },
    {
      id: 1,
      stepLabel: '02',
      title: 'Authenticated Local Transport',
      subtitle: 'Port 8090 • Bearer Token • Monotonic Sequence',
      latency: '~4.5 ms Wi-Fi',
      shortDesc:
        'JSON wire packets travel over local Wi-Fi or USB-C with strict monotonic sequence verification.',
      details: [
        'Routes: POST /v1/events, POST /v1/battery, POST /v1/download, and POST /v1/display-mode.',
        'Protected by a 16+ hex character Bearer token stored only in local git-ignored config.',
        'The receiver enforces strictly increasing sequence numbers per job; duplicates or stale packets are rejected.',
        'Network hiccups trigger exponential backoff and never falsely mark a local build as failed.',
      ],
      codeSnippet: `POST /v1/events HTTP/1.0
Host: 192.168.1.5:8090
Authorization: Bearer <shared_token>
Content-Type: application/json

{
  "schema_version": 1,
  "event": "progress",
  "job_id": "build-x86-092",
  "sequence": 18,
  "elapsed_seconds": 12.4,
  "progress": 38,
  "is_failure": false
}`,
    },
    {
      id: 2,
      stepLabel: '03',
      title: 'QRB2210 Linux State Engine',
      subtitle: 'Priority Arbitration • 6.0s Watchdog • SQLite Store',
      latency: '0.8 ms eval',
      shortDesc:
        'The UNO Q Linux processor arbitrates priority, detects 6-second heartbeat stalls, and archives runs.',
      details: [
        'uno-q/receiver.py runs a lightweight ThreadingHTTPServer on port 8090.',
        'StateEngine prioritizes active Chrome downloads and active or failed jobs over passive battery updates.',
        'If 6.0 seconds pass without a heartbeat, the state engine transitions to suspected_stall.',
        'history_store.py records completed and failed sessions to SQLite across board restarts.',
      ],
      codeSnippet: `# uno-q/app_lab_main.py bridges Linux receiver to STM32:
lights = fetch_verified_lights("http://127.0.0.1:8090/v1/lights", token)
Bridge.call("set_job_lights", lights["code"], lights["progress"])`,
    },
    {
      id: 3,
      stepLabel: '04',
      title: 'STM32U585 Optical Matrix',
      subtitle: '104 Blue LEDs • 3-Bit Grayscale • RGB LED 3',
      latency: '60 Hz refresh',
      shortDesc:
        'The microcontroller drives 104 blue LEDs and companion RGB LED 3 using non-blocking millis() loops.',
      details: [
        'All animations (heart pulses, stepping dots, charging bars) run on hardware millis() clocks.',
        'The 8×13 matrix renders 3-bit grayscale (0..7) with custom 3×5 numerals and a 13-LED 100% bar.',
        'Companion RGB LED 3 provides instant semantic color: blue pulse, warm amber, steady red, or green.',
        'Animations stay silky-smooth at 60Hz without blocking HTTP or Bridge calls.',
      ],
      codeSnippet: `void set_job_lights(int code, int progress) {
  current_state_code = code;
  current_progress = constrain(progress, 0, 100);
  // Non-blocking frame evaluation in loop() via millis()
  render_matrix_frame(current_state_code, current_progress, millis());
}`,
    },
    {
      id: 4,
      stepLabel: '05',
      title: 'Read-Only Web & CLI Relay',
      subtitle: 'Sanitized Telemetry • Zero Exposed Credentials',
      latency: 'Read-only JSON',
      shortDesc:
        'Serves sanitized snapshots to the web Control Deck and ANSI terminal monitor without exposing secrets.',
      details: [
        'Board IP addresses and bearer tokens never enter browser JavaScript.',
        'Local filesystem paths are stripped from Chrome download filenames before serving.',
        'Powers both this web dashboard and the zero-dependency mac-agent/terminal_monitor.py.',
        'Gracefully falls back to deterministic interactive simulations when hardware is offline.',
      ],
      codeSnippet: `GET /api/telemetry HTTP/1.1
HTTP/1.1 200 OK
Content-Type: application/json

{
  "is_live": true,
  "battery": { "percent": 82, "charging_state": "discharging" },
  "lights": { "state": "battery", "code": 6, "progress": 82 }
}`,
    },
  ];

  useEffect(() => {
    if (!packetAnimating) return;
    const timer = setInterval(() => {
      setActiveStep((prev) => {
        if (prev >= steps.length - 1) {
          setPacketAnimating(false);
          return prev;
        }
        return prev + 1;
      });
    }, 620);
    return () => clearInterval(timer);
  }, [packetAnimating, steps.length]);

  const handleTracePacket = () => {
    setActiveStep(0);
    setPacketAnimating(true);
  };

  const handleCopySnippet = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(steps[activeStep].codeSnippet);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  return (
    <section
      id="how-it-works"
      className="py-16 sm:py-24 bg-[#F1F0EC] dark:bg-[#131519] border-b border-black/[0.08] dark:border-white/[0.08]"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        {/* Section Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-2 max-w-2xl">
            <div className="text-xs font-mono uppercase tracking-wider text-[#0055FF] dark:text-[#38BDF8] font-semibold">
              System Architecture
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-[-0.035em] text-[#141517] dark:text-white leading-[1.06]">
              Five disciplined layers.{' '}
              <span className="font-serif italic font-normal text-[#4A4D52] dark:text-[#9CA3AF]">
                Under twenty milliseconds.
              </span>
            </h2>
          </div>

          <button
            onClick={handleTracePacket}
            disabled={packetAnimating}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-semibold bg-[#141517] hover:bg-[#0055FF] dark:bg-white dark:hover:bg-[#38BDF8] disabled:opacity-60 text-white dark:text-[#141517] transition-colors self-start lg:self-auto"
          >
            <Send className={`w-3.5 h-3.5 ${packetAnimating ? 'animate-ping' : ''}`} />
            <span>{packetAnimating ? 'Tracing Signal Path...' : 'Trace Live Signal Path'}</span>
          </button>
        </div>

        {/* Joined Architectural Pipeline & Code Inspector */}
        <div className="arch-grid">
          {/* Top 5-Step Pipeline Selector Row */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-[1px] bg-black/[0.08] dark:bg-white/[0.08]">
            {steps.map((s, idx) => {
              const isCurrent = activeStep === idx;
              return (
                <button
                  key={s.id}
                  onClick={() => {
                    setPacketAnimating(false);
                    setActiveStep(idx);
                  }}
                  className={`text-left p-4 sm:p-5 transition-colors flex flex-col justify-between ${
                    isCurrent
                      ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517]'
                      : 'arch-cell text-[#4A4D52] dark:text-[#9CA3AF] hover:bg-[#F9F9F8] dark:hover:bg-[#1E2229]'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between text-xs font-mono mb-2">
                      <span className={isCurrent ? 'text-[#38BDF8] dark:text-[#0055FF] font-bold' : 'text-[#787C82]'}>
                        STAGE {s.stepLabel}
                      </span>
                      <span className="text-[11px] opacity-75">{s.latency}</span>
                    </div>
                    <div className="text-sm font-bold leading-snug text-inherit">
                      {s.title}
                    </div>
                  </div>
                  <div className="text-[11px] mt-2 opacity-75 truncate">
                    {s.subtitle}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Bottom Split: Left Guarantees (7 cols) + Right Wire Code (5 cols) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-[1px] bg-black/[0.08] dark:bg-white/[0.08]">
            <div className="lg:col-span-7 arch-cell p-6 sm:p-8 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-xs font-mono text-[#787C82] mb-2">
                  <span>STAGE {steps[activeStep].stepLabel} // {steps[activeStep].subtitle.toUpperCase()}</span>
                  <span>{steps[activeStep].latency}</span>
                </div>

                <h3 className="text-2xl font-bold text-[#141517] dark:text-white mb-2">
                  {steps[activeStep].title}
                </h3>
                <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed mb-5">
                  {steps[activeStep].shortDesc}
                </p>

                <div className="space-y-2 mb-6">
                  {steps[activeStep].details.map((point, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 p-3 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] text-xs sm:text-sm text-[#141517] dark:text-slate-200"
                    >
                      <CheckCircle2 className="w-4 h-4 text-[#0055FF] dark:text-[#38BDF8] shrink-0 mt-0.5" />
                      <span>{point}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-black/[0.07] dark:border-white/10 text-xs font-semibold">
                <button
                  disabled={activeStep === 0}
                  onClick={() => setActiveStep((prev) => Math.max(0, prev - 1))}
                  className="px-3.5 py-1.5 rounded-lg bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white disabled:opacity-35 disabled:pointer-events-none"
                >
                  ← Previous
                </button>
                <span className="font-mono text-[#787C82]">
                  {activeStep + 1} / {steps.length}
                </span>
                <button
                  disabled={activeStep === steps.length - 1}
                  onClick={() =>
                    setActiveStep((prev) => Math.min(steps.length - 1, prev + 1))
                  }
                  className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-lg bg-[#141517] dark:bg-white text-white dark:text-[#141517] disabled:opacity-35 disabled:pointer-events-none"
                >
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="lg:col-span-5 bg-[#141517] text-white p-6 sm:p-8 flex flex-col justify-between font-mono text-xs">
              <div>
                <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/10">
                  <span className="text-slate-300 font-semibold">
                    STAGE {steps[activeStep].stepLabel} INTERFACE CONTRACT
                  </span>
                  <button
                    onClick={handleCopySnippet}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-slate-200 text-[11px] transition-colors"
                  >
                    {copiedCode ? (
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

                <pre className="p-4 rounded-lg bg-black/50 border border-white/[0.08] text-slate-200 overflow-x-auto text-[11px] leading-relaxed whitespace-pre-wrap select-text">
                  {steps[activeStep].codeSnippet}
                </pre>
              </div>

              <div className="mt-6 pt-4 border-t border-white/10 space-y-1.5 text-[11px] text-slate-400">
                <div className="flex items-center justify-between">
                  <span>External Dependencies</span>
                  <span className="text-white font-semibold">0 (Python Stdlib)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Authorization</span>
                  <span className="text-white font-semibold">Bearer (16+ Hex)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>End-to-End Latency</span>
                  <span className="text-emerald-400 font-semibold">&lt; 20ms Mac-to-LED</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
