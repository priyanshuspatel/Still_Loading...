import React from 'react';
import { Cpu, Server, ShieldCheck, CheckCircle2 } from 'lucide-react';

export const TechnicalSpecs: React.FC = () => {
  const hardwareSpecs = [
    { label: 'Application Processor', value: 'Qualcomm QRB2210 (Quad-core ARM Cortex-A53 @ 2.0 GHz)' },
    { label: 'Microcontroller Core', value: 'STMicroelectronics STM32U585 (ARM Cortex-M33)' },
    { label: 'Onboard Matrix Display', value: '8 rows × 13 columns (104 blue LEDs, 3-bit grayscale 0..7)' },
    { label: 'Companion Status LED', value: 'RGB LED 3 (PH10–PH12 active-low PWM controlled)' },
    { label: 'Inter-Processor Bus', value: 'Arduino Router Bridge (Linux Python to STM32 Sketch)' },
    { label: 'Wireless Networking', value: 'Wi-Fi 5 (802.11ac dual-band) + Bluetooth 5.0' },
    { label: 'Power & Programming', value: 'USB-C (Power Delivery + High-Speed Data)' },
  ];

  const softwareSpecs = [
    { label: 'macOS Agent Runtime', value: 'Python 3.11+ (Standard Library, zero external pip packages)' },
    { label: 'Battery Monitor', value: 'pmset -g batt parser (15s poll, 5m periodic refresh, backoff)' },
    { label: 'Chrome Download Monitor', value: 'Real-time percentage and byte observer via .crdownload' },
    { label: 'Job Process Runner', value: 'run_job.py (Streams stdout/stderr off-wire; captures exit codes)' },
    { label: 'Network Receiver', value: 'Python ThreadingHTTPServer listening on port 8090' },
    { label: 'Wire Message Protocol', value: 'JSON Schema Version 1 (Strict monotonic sequence numbers)' },
    { label: 'Security & Auth', value: 'Bearer token authorization (minimum 16 hex characters)' },
    { label: 'Automated Test Suite', value: '74 unit tests covering protocol, matrix bitmaps, and state engine' },
  ];

  const apiEndpoints = [
    { method: 'POST', path: '/v1/battery', desc: 'Sends validated MacBook battery readings & charging state' },
    { method: 'POST', path: '/v1/download', desc: 'Sends Chrome download progress, byte counts, and status' },
    { method: 'POST', path: '/v1/events', desc: 'Wire events: started, heartbeat, progress, failed, completed' },
    { method: 'POST', path: '/v1/display-mode', desc: 'Sets priority display mode: auto, job, or battery' },
    { method: 'GET', path: '/v1/lights', desc: 'Returns active light code, progress, and display state' },
    { method: 'GET', path: '/health', desc: 'Liveness probe returning status: ok (no job data)' },
  ];

  return (
    <section className="py-20 bg-graphite-950/40 border-t border-white/[0.04]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-14 text-center sm:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-graphite-900 border border-white/10 text-xs font-mono text-graphite-300 mb-3">
            <span>Engineering Specifications</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4">
            Technical Architecture & Rigor
          </h2>
          <p className="text-base sm:text-lg text-graphite-400 leading-relaxed">
            Every specification is verified against the real code and hardware. Built with zero bloated dependencies and complete respect for battery and network resources.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          {/* Hardware Specs */}
          <div className="p-6 sm:p-8 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel">
            <div className="flex items-center gap-3 pb-4 mb-6 border-b border-white/[0.08]">
              <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Hardware Matrix & Board</h3>
                <span className="text-xs font-mono text-graphite-400">Arduino UNO Q Specifications</span>
              </div>
            </div>

            <dl className="space-y-3 font-mono text-xs">
              {hardwareSpecs.map((spec) => (
                <div key={spec.label} className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-white/[0.04] gap-1">
                  <dt className="text-graphite-400">{spec.label}</dt>
                  <dd className="text-white font-medium sm:text-right">{spec.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Software Specs */}
          <div className="p-6 sm:p-8 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel">
            <div className="flex items-center gap-3 pb-4 mb-6 border-b border-white/[0.08]">
              <div className="p-2.5 rounded-xl bg-accent-lime/10 text-accent-lime border border-accent-lime/20">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Software & Firmware Stack</h3>
                <span className="text-xs font-mono text-graphite-400">Python 3 + Arduino C++ Firmware</span>
              </div>
            </div>

            <dl className="space-y-3 font-mono text-xs">
              {softwareSpecs.map((spec) => (
                <div key={spec.label} className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-white/[0.04] gap-1">
                  <dt className="text-graphite-400">{spec.label}</dt>
                  <dd className="text-white font-medium sm:text-right">{spec.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        {/* API Routes Table */}
        <div className="p-6 sm:p-8 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel">
          <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Verified Receiver API Routes</h3>
                <span className="text-xs font-mono text-graphite-400">Listening on port 8090 (Bearer Token Required)</span>
              </div>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-white/5 text-accent-lime border border-white/10">
              HTTP/1.0 Standard
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-graphite-400">
                  <th className="pb-3 font-semibold">METHOD</th>
                  <th className="pb-3 font-semibold">ROUTE</th>
                  <th className="pb-3 font-semibold">DESCRIPTION</th>
                  <th className="pb-3 font-semibold">AUTH</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {apiEndpoints.map((ep) => (
                  <tr key={ep.path} className="hover:bg-white/[0.02]">
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                        ep.method === 'POST'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-led-blue/20 text-led-blue border border-led-blue/30'
                      }`}>
                        {ep.method}
                      </span>
                    </td>
                    <td className="py-3 text-white font-medium">{ep.path}</td>
                    <td className="py-3 text-graphite-400">{ep.desc}</td>
                    <td className="py-3 text-graphite-500">
                      {ep.path === '/health' ? 'Public' : 'Bearer Token'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
};
