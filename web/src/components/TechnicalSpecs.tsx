import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';

export const TechnicalSpecs: React.FC = () => {
  const [copiedRoute, setCopiedRoute] = useState<string | null>(null);

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
    { label: 'Job Process Runner', value: 'run_job.py (Streams stdout/stderr off-wire; 512B redacted excerpt)' },
    { label: 'Network Receiver', value: 'Python ThreadingHTTPServer + SQLite history_store.py (Port 8090)' },
    { label: 'Wire Message Protocol', value: 'JSON Schema Version 1 (Strict monotonic sequence numbers)' },
    { label: 'Security & Auth', value: 'Bearer token authorization (minimum 16 hex characters)' },
    { label: 'Automated Test Suite', value: '178 verified tests (172 Mac + 2 Relay + 4 Web Matrix Engine)' },
  ];

  const apiEndpoints = [
    {
      method: 'POST',
      path: '/v1/events',
      desc: 'Wire events: started, heartbeat, progress, failed (with excerpt), completed',
      curl: `curl -X POST http://127.0.0.1:8090/v1/events -H "Authorization: Bearer $STILL_LOADING_TOKEN" -H "Content-Type: application/json" -d '{"schema_version":1,"event":"started","job_id":"demo01","sequence":1,"timestamp":"2026-10-27T00:00:00Z","elapsed_seconds":0,"progress":0,"is_failure":false}'`,
    },
    {
      method: 'POST',
      path: '/v1/battery',
      desc: 'Validates & stores MacBook battery percentage and charging state',
      curl: `curl -X POST http://127.0.0.1:8090/v1/battery -H "Authorization: Bearer $STILL_LOADING_TOKEN" -H "Content-Type: application/json" -d '{"schema_version":1,"percent":82,"charging_state":"discharging"}'`,
    },
    {
      method: 'POST',
      path: '/v1/download',
      desc: 'Validates & stores Chrome .crdownload transfer progress & byte counts',
      curl: `curl -X POST http://127.0.0.1:8090/v1/download -H "Authorization: Bearer $STILL_LOADING_TOKEN" -H "Content-Type: application/json" -d '{"schema_version":1,"active":true,"state":"downloading","progress":68,"progress_known":true,"downloaded_bytes":680000,"total_bytes":1000000}'`,
    },
    {
      method: 'POST',
      path: '/v1/display-mode',
      desc: 'Selects display priority arbitration mode: auto, job, or battery',
      curl: `curl -X POST http://127.0.0.1:8090/v1/display-mode -H "Authorization: Bearer $STILL_LOADING_TOKEN" -H "Content-Type: application/json" -d '{"mode":"auto"}'`,
    },
    {
      method: 'GET',
      path: '/v1/lights',
      desc: 'Returns active hardware light code (0..9), progress, and display state',
      curl: `curl -H "Authorization: Bearer $STILL_LOADING_TOKEN" http://127.0.0.1:8090/v1/lights`,
    },
    {
      method: 'GET',
      path: '/v1/history',
      desc: 'Queries persistent SQLite job execution runs and failure diagnostics',
      curl: `curl -H "Authorization: Bearer $STILL_LOADING_TOKEN" "http://127.0.0.1:8090/v1/history?limit=20"`,
    },
    {
      method: 'GET',
      path: '/health',
      desc: 'Public unauthenticated liveness probe returning {"status":"ok"}',
      curl: `curl http://127.0.0.1:8090/health`,
    },
  ];

  const handleCopyCurl = (path: string, curl: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(curl);
      setCopiedRoute(path);
      setTimeout(() => setCopiedRoute(null), 2000);
    }
  };

  return (
    <section className="py-16 sm:py-24 bg-[#F9F9F8] dark:bg-[#0C0D0F] border-b border-black/[0.08] dark:border-white/[0.08]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="space-y-2 max-w-2xl">
          <div className="text-xs font-mono uppercase tracking-wider text-[#0055FF] dark:text-[#38BDF8] font-semibold">
            Engineering Datasheet
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-[-0.035em] text-[#141517] dark:text-white leading-[1.06]">
            Engineered with{' '}
            <span className="font-serif italic font-normal text-[#4A4D52] dark:text-[#9CA3AF]">
              nothing to hide.
            </span>
          </h2>
        </div>

        {/* Joined Architectural Datasheet */}
        <div className="arch-grid">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-[1px] bg-black/[0.08] dark:bg-white/[0.08]">
            {/* Hardware Column */}
            <div className="arch-cell p-6 sm:p-8">
              <div className="text-xs font-mono uppercase tracking-wider text-[#787C82] mb-4">
                01 // HARDWARE ARCHITECTURE (ARDUINO UNO Q)
              </div>
              <dl className="divide-y divide-black/[0.06] dark:divide-white/[0.06] text-xs sm:text-sm">
                {hardwareSpecs.map((spec) => (
                  <div
                    key={spec.label}
                    className="flex flex-col sm:flex-row sm:items-center justify-between py-3 gap-1"
                  >
                    <dt className="text-[#787C82]">{spec.label}</dt>
                    <dd className="text-[#141517] dark:text-white font-semibold sm:text-right">
                      {spec.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* Software Column */}
            <div className="arch-cell p-6 sm:p-8">
              <div className="text-xs font-mono uppercase tracking-wider text-[#787C82] mb-4">
                02 // RUNTIME & VERIFICATION STACK
              </div>
              <dl className="divide-y divide-black/[0.06] dark:divide-white/[0.06] text-xs sm:text-sm">
                {softwareSpecs.map((spec) => (
                  <div
                    key={spec.label}
                    className="flex flex-col sm:flex-row sm:items-center justify-between py-3 gap-1"
                  >
                    <dt className="text-[#787C82]">{spec.label}</dt>
                    <dd className="text-[#141517] dark:text-white font-semibold sm:text-right">
                      {spec.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>

          {/* Receiver API Ledger */}
          <div className="arch-cell p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <span className="text-xs font-mono uppercase tracking-wider text-[#787C82]">
                03 // VERIFIED RECEIVER HTTP/1.0 WIRE ENDPOINTS (PORT 8090)
              </span>
              <span className="text-xs font-mono text-[#787C82]">
                Click any route for ready-to-run cURL probe
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-black/[0.08] dark:border-white/10 text-[#787C82] font-mono uppercase text-[11px]">
                    <th className="pb-2.5 font-semibold">Method</th>
                    <th className="pb-2.5 font-semibold">Route</th>
                    <th className="pb-2.5 font-semibold">Specification</th>
                    <th className="pb-2.5 font-semibold">Auth</th>
                    <th className="pb-2.5 text-right font-semibold">Probe</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/[0.06] dark:divide-white/[0.06]">
                  {apiEndpoints.map((ep) => (
                    <tr key={ep.path}>
                      <td className="py-3 pr-3 font-mono">
                        <span
                          className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                            ep.method === 'POST'
                              ? 'bg-[#0055FF]/10 text-[#0055FF] dark:text-[#38BDF8]'
                              : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                          }`}
                        >
                          {ep.method}
                        </span>
                      </td>
                      <td className="py-3 pr-4 font-mono text-[#141517] dark:text-white font-bold">
                        {ep.path}
                      </td>
                      <td className="py-3 pr-4 text-[#4A4D52] dark:text-[#9CA3AF]">
                        {ep.desc}
                      </td>
                      <td className="py-3 pr-4 font-mono text-[11px] text-[#787C82]">
                        {ep.path === '/health' ? 'Public' : 'Bearer'}
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => handleCopyCurl(ep.path, ep.curl)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-[#F1F0EC] hover:bg-[#141517] hover:text-white dark:bg-white/10 dark:hover:bg-white dark:hover:text-[#141517] text-[#141517] dark:text-white text-[11px] font-mono font-semibold transition-colors"
                        >
                          {copiedRoute === ep.path ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-500" />
                              <span>Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>cURL</span>
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
