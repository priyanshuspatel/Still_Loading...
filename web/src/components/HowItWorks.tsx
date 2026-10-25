import React, { useState } from 'react';
import { Laptop, Cpu, Radio, Shield, Terminal, ArrowRight, CheckCircle2, ChevronRight } from 'lucide-react';

export const HowItWorks: React.FC = () => {
  const [activeStep, setActiveStep] = useState<number>(0);

  const steps = [
    {
      id: 0,
      badge: 'Step 1 • macOS Agent',
      title: 'Monitors macOS Battery & Chrome Downloads',
      icon: <Laptop className="w-5 h-5 text-led-blue" />,
      shortDesc: 'mac-agent runs Python-based observers using standard macOS utilities.',
      details: [
        'battery_monitor.py executes pmset -g batt every 15s to parse charge % and AC adapter state.',
        'download_monitor.py detects Chrome download files (.crdownload) and tracks transfer rates.',
        'run_job.py captures arbitrary command-line subprocesses and extracts percentage markers.',
        'Emits validated JSON wire messages conforming to shared/message_schema.json.',
      ],
      codeSnippet: `// Terminal command on Mac:
python3 mac-agent/battery_monitor.py --mode auto --config config.local.json
// Or watch an arbitrary command:
python3 mac-agent/run_job.py --send -- python3 build.py`,
    },
    {
      id: 1,
      badge: 'Step 2 • Transport',
      title: 'Authenticated Local HTTP to Port 8090',
      icon: <Radio className="w-5 h-5 text-accent-lime" />,
      shortDesc: 'Mac sends JSON payloads over local Wi-Fi to the UNO Q device.',
      details: [
        'Endpoint routes: POST /v1/battery, POST /v1/download, POST /v1/events.',
        'Protected by Bearer Token (minimum 16 hex characters, stored in config.local.json).',
        'Receiver keeps strictly monotonic sequence numbers to refuse duplicate or stale packets.',
        'Network delivery errors are handled with exponential backoff and never false-flag a job as failed.',
      ],
      codeSnippet: `POST /v1/battery HTTP/1.0
Authorization: Bearer <shared_token>
Content-Type: application/json

{"schema_version": 1, "percent": 82, "charging_state": "discharging"}`,
    },
    {
      id: 2,
      badge: 'Step 3 • Receiver & State Engine',
      title: 'UNO Q Debian Linux & State Engine',
      icon: <Cpu className="w-5 h-5 text-sky-400" />,
      shortDesc: 'Qualcomm QRB2210 processor coordinates priority and display modes.',
      details: [
        'uno-q/receiver.py runs on Linux userland listening on 0.0.0.0:8090.',
        'StateEngine enforces display priority: active Chrome download > active job > MacBook battery.',
        'Missing heartbeat triggers suspected_stall on receiver clock after 6.0 seconds.',
        'App Lab companion polls GET /v1/lights and invokes Bridge.call("set_job_lights", code, progress).',
      ],
      codeSnippet: `lights = engine.view
# Bridge call to microcontroller:
Bridge.call("set_job_lights", lights.code, lights.progress)`,
    },
    {
      id: 3,
      badge: 'Step 4 • Microcontroller Display',
      title: 'STM32U585 Drives 8×13 LED Matrix & LED 3',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
      shortDesc: 'Microcontroller hardware renders 104 blue LEDs and RGB status light.',
      details: [
        'All animations run on non-blocking millis() timing on the microcontroller.',
        'Companion RGB LED 3 conveys state color (blue pulse, amber, red error, calm green).',
        '8×13 Matrix displays 3-bit grayscale typography, breathing hearts, or framed [ ! ] alerts.',
        '3×5 font with special 100% full-width row 7 completion bar.',
      ],
      codeSnippet: `void set_job_lights(int code, int progress) {
  current_code = code;
  current_progress = progress;
  // Non-blocking frame updates using millis()
}`,
    },
    {
      id: 4,
      badge: 'Step 5 • Public Telemetry Relay',
      title: 'Sanitized Read-Only Web Gateway',
      icon: <Shield className="w-5 h-5 text-purple-400" />,
      shortDesc: 'stillloading.tech connects securely without exposing private local networks.',
      details: [
        'Hardware receiver is never exposed nakedly to the public internet.',
        'A secure cloud telemetry relay forwards sanitized JSON snapshots to stillloading.tech.',
        'Private filepaths and tokens are stripped on the server side.',
        'Visitors can explore the live system or full interactive demo with complete safety.',
      ],
      codeSnippet: `GET /api/telemetry -> 200 OK
{
  "battery": {"percent": 82, "charging_state": "discharging"},
  "lights": {"state": "battery", "code": 6}
}`,
    },
  ];

  return (
    <section id="how-it-works" className="py-24 bg-graphite-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="max-w-3xl mb-16 text-center sm:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-graphite-900 border border-white/10 text-xs font-mono text-graphite-300 mb-3">
            <span>System Architecture</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4">
            From macOS process to physical silicon light.
          </h2>
          <p className="text-base sm:text-lg text-graphite-400 leading-relaxed">
            Still Loading... connects five disciplined layers. Here is the exact data flow from your MacBook’s battery or Chrome browser to the physical 8×13 LED matrix.
          </p>
        </div>

        {/* High-Level Architecture Flow Diagram (Visual Pipeline) */}
        <div className="mb-14 p-6 sm:p-8 rounded-2xl bg-gradient-to-b from-graphite-900/90 to-graphite-950 border border-white/10 shadow-panel">
          <div className="flex items-center justify-between text-xs font-mono text-graphite-400 border-b border-white/[0.08] pb-4 mb-6">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-led-blue" />
              <span>END-TO-END PIPELINE DIAGRAM</span>
            </span>
            <span className="hidden sm:inline text-graphite-500">LOCAL HARDWARE + PUBLIC RELAY</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
            {steps.map((s, idx) => (
              <button
                key={s.id}
                onClick={() => setActiveStep(idx)}
                className={`text-left p-4 rounded-xl border transition-all duration-200 relative ${
                  activeStep === idx
                    ? 'bg-graphite-800/90 border-led-blue/60 shadow-panel scale-[1.02]'
                    : 'bg-graphite-900/60 border-white/[0.06] hover:border-white/20'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 rounded-lg bg-black/40">{s.icon}</div>
                  <span className="text-[10px] font-mono text-graphite-400">0{idx + 1}</span>
                </div>
                <div className="text-xs font-semibold text-white mb-1">{s.title.split(' ')[0]} {s.title.split(' ')[1]}</div>
                <div className="text-[11px] text-graphite-400 line-clamp-2">{s.shortDesc}</div>
                {activeStep === idx && (
                  <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-led-blue rotate-45 rounded-sm" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Detailed Step Inspector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left: Step Breakdown */}
          <div className="lg:col-span-7 space-y-6">
            <div className="p-6 sm:p-8 rounded-2xl bg-graphite-900/70 border border-white/10">
              <div className="flex items-center gap-3 mb-4">
                <span className="px-2.5 py-1 rounded text-xs font-mono bg-led-blue/10 text-led-blue border border-led-blue/30 font-semibold">
                  {steps[activeStep].badge}
                </span>
                <span className="text-xs font-mono text-graphite-500">Phase Verified</span>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                {steps[activeStep].title}
              </h3>
              <p className="text-sm text-graphite-300 leading-relaxed mb-6">
                {steps[activeStep].shortDesc}
              </p>

              <div className="space-y-3 mb-6">
                <div className="text-xs font-mono uppercase text-graphite-400 tracking-wider">
                  Key Technical Guarantees:
                </div>
                {steps[activeStep].details.map((point, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-sm text-graphite-300">
                    <CheckCircle2 className="w-4 h-4 text-accent-lime shrink-0 mt-0.5" />
                    <span>{point}</span>
                  </div>
                ))}
              </div>

              {/* Step Navigation Controls */}
              <div className="flex items-center justify-between pt-4 border-t border-white/[0.06]">
                <button
                  disabled={activeStep === 0}
                  onClick={() => setActiveStep((prev) => Math.max(0, prev - 1))}
                  className="px-3 py-1.5 rounded-lg text-xs font-mono text-graphite-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none"
                >
                  ← Previous Layer
                </button>
                <span className="text-xs font-mono text-graphite-500">
                  {activeStep + 1} of {steps.length}
                </span>
                <button
                  disabled={activeStep === steps.length - 1}
                  onClick={() => setActiveStep((prev) => Math.min(steps.length - 1, prev + 1))}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-mono text-led-blue hover:text-sky-300 font-semibold disabled:opacity-30 disabled:pointer-events-none"
                >
                  <span>Next Layer</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Right: Code & Protocol Contract */}
          <div className="lg:col-span-5 space-y-4">
            <div className="p-5 sm:p-6 rounded-2xl bg-graphite-950 border border-white/10 shadow-2xl font-mono text-xs">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/[0.08] text-graphite-400">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-accent-lime" />
                  <span className="text-white text-xs font-medium">Protocol / Interface Contract</span>
                </div>
                <span className="text-[10px] text-graphite-500">VERIFIED CODE</span>
              </div>

              <pre className="p-4 rounded-xl bg-black/60 border border-white/5 text-graphite-200 overflow-x-auto text-[11px] leading-relaxed whitespace-pre-wrap">
                {steps[activeStep].codeSnippet}
              </pre>

              <div className="mt-4 pt-3 border-t border-white/5 text-[11px] text-graphite-400 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-graphite-500">Security:</span>
                  <span className="text-graphite-200">Zero Public Write Endpoints</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-graphite-500">Network:</span>
                  <span className="text-graphite-200">Local Wi-Fi or USB Bridge</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-graphite-500">Latency:</span>
                  <span className="text-accent-lime">&lt; 20ms Mac-to-Matrix</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
