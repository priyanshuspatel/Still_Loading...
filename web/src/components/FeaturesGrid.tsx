import React from 'react';
import { BatteryCharging, Download, Cpu, ShieldCheck, Activity, Terminal } from 'lucide-react';

export const FeaturesGrid: React.FC = () => {
  const features = [
    {
      icon: <BatteryCharging className="w-5 h-5 text-accent-lime" />,
      tag: 'Continuous Gauge',
      title: 'MacBook Battery Telemetry',
      description:
        'Continuous background polling via macOS pmset. Tracks exact charge percentage, AC charging, discharging, or full status. Renders live numerical % with animated bottom charging scanlines.',
      details: '15s default check • 5m auto-refresh • Resilient backoff • Clamshell sleep safety',
    },
    {
      icon: <Download className="w-5 h-5 text-led-blue" />,
      tag: 'Real-Time Progress',
      title: 'Chrome Download Monitor',
      description:
        'Detects active Chrome download streams and forwards instantaneous percentage and transfer byte stats. Takes priority over idle desk displays so you never miss a completed file.',
      details: 'Bytes transferred • Estimated speed • Sanitized metadata • Clean idle fallback',
    },
    {
      icon: <Cpu className="w-5 h-5 text-sky-400" />,
      tag: '104 Physical LEDs',
      title: '8×13 Blue Matrix & RGB LED 3',
      description:
        'Mathematical 3-bit grayscale (brightness levels 0..7). Custom 3×5 proportional typography with custom 100% full-bar layout, calm breathing hearts, and distinct [ ! ] warning frames.',
      details: 'STM32U585 driven • Zero HTTP blocking • Non-blocking millis() rendering',
    },
    {
      icon: <Terminal className="w-5 h-5 text-amber-400" />,
      tag: 'Command-Line Companion',
      title: 'Arbitrary Job Monitoring',
      description:
        'Watch long-running compile commands, AI scripts, or test suites via run_job.py. Emits wire events: started, heartbeat, progress, completed, and failed with captured exit codes.',
      details: 'Stdout/stderr kept off wire • Heartbeat liveness • Fast fail detection',
    },
    {
      icon: <Activity className="w-5 h-5 text-purple-400" />,
      tag: 'State Machine',
      title: 'Independent State Engine',
      description:
        'The UNO Q receiver maintains its own clock. Missing heartbeats trigger a suspected_stall state without declaring failure. The system recovers smoothly as soon as progress resumes.',
      details: 'Strict monotonic sequence checks • Priority display modes: auto, job, battery',
    },
    {
      icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
      tag: 'Local-First Security',
      title: 'Protected Local Transport',
      description:
        'Communication runs locally over HTTP with bearer tokens. Zero cloud dependencies. Public telemetry is strictly read-only and sanitized to protect private file paths and device secrets.',
      details: '16+ character bearer tokens • Localhost loopback testing • No open proxies',
    },
  ];

  return (
    <section className="py-20 bg-graphite-950/60 border-t border-b border-white/[0.04]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="max-w-3xl mb-16 text-center sm:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-graphite-900 border border-white/10 text-xs font-mono text-graphite-300 mb-3">
            <span>Capabilities</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4">
            Engineered for precision. Built for real waiting.
          </h2>
          <p className="text-base sm:text-lg text-graphite-400 leading-relaxed">
            Every feature in Still Loading... serves a practical desk function. No fabricated percentages, no generic dashboards, and no bloated cloud requirements.
          </p>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feat) => (
            <div
              key={feat.title}
              className="group relative p-6 rounded-2xl bg-gradient-to-b from-graphite-900/80 to-graphite-950 border border-white/[0.07] hover:border-white/[0.15] hover:shadow-panel transition-all duration-300 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="p-2.5 rounded-xl bg-graphite-800/80 border border-white/10 group-hover:border-led-blue/40 transition-colors">
                    {feat.icon}
                  </div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-graphite-400 bg-white/[0.03] px-2 py-0.5 rounded border border-white/5">
                    {feat.tag}
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-led-blue transition-colors">
                  {feat.title}
                </h3>
                <p className="text-sm text-graphite-400 leading-relaxed mb-4">
                  {feat.description}
                </p>
              </div>

              <div className="pt-3 border-t border-white/[0.06] text-[11px] font-mono text-graphite-500">
                {feat.details}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
