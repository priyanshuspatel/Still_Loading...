import React, { useState } from 'react';
import { X, ShieldCheck, Radio, Server, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { DEFAULT_TELEMETRY_CONFIG } from '../lib/telemetryClient';

interface LiveConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onEndpointChange?: (newUrl: string) => void;
}

export const LiveConnectionModal: React.FC<LiveConnectionModalProps> = ({
  isOpen,
  onClose,
  onEndpointChange,
}) => {
  const [endpoint, setEndpoint] = useState(DEFAULT_TELEMETRY_CONFIG.endpointUrl);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState<string>('');

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setTestMessage('Pinging telemetry endpoint...');
    try {
      const res = await fetch(endpoint, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (res.ok) {
        setTestStatus('success');
        setTestMessage(`Endpoint verified! Responded with HTTP ${res.status}.`);
        if (onEndpointChange) onEndpointChange(endpoint);
      } else {
        setTestStatus('error');
        setTestMessage(`Server returned HTTP ${res.status} (${res.statusText}).`);
      }
    } catch (err: any) {
      setTestStatus('error');
      setTestMessage(err.message || 'Failed to reach endpoint. Cross-Origin or Network Error.');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="relative w-full max-w-lg p-6 sm:p-8 rounded-2xl bg-graphite-900 border border-white/10 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-led-blue/10 text-led-blue border border-led-blue/20">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 id="modal-title" className="text-lg font-bold text-white">
                Live Telemetry Gateway
              </h3>
              <p className="text-xs font-mono text-graphite-400">
                Configure live read-only telemetry connection
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-graphite-400 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Security Notice */}
        <div className="p-4 rounded-xl bg-purple-950/30 border border-purple-500/20 text-xs font-mono text-purple-200 space-y-2">
          <div className="flex items-center gap-2 text-purple-300 font-semibold">
            <ShieldCheck className="w-4 h-4 text-accent-lime" />
            <span>Strict Browser Security Boundary</span>
          </div>
          <p className="leading-relaxed text-graphite-300">
            Private bearer tokens and internal device IPs (like 192.168.1.5) are <strong>never</strong> exposed in frontend JavaScript.
            The web dashboard connects to a secure, sanitized read-only proxy relay.
          </p>
        </div>

        {/* Endpoint Input */}
        <div className="space-y-2">
          <label className="block text-xs font-mono text-graphite-300 font-medium">
            Telemetry Relay URL:
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="/api/telemetry or https://relay.stillloading.tech/api/telemetry"
              className="w-full px-3.5 py-2.5 rounded-xl bg-graphite-950 border border-white/10 text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-led-blue focus:border-transparent"
            />
            <button
              onClick={handleTestConnection}
              disabled={testStatus === 'testing'}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-graphite-800 hover:bg-graphite-700 text-graphite-200 border border-white/10 text-xs font-mono font-medium disabled:opacity-50 shrink-0"
            >
              {testStatus === 'testing' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-led-blue" />
              ) : (
                <Radio className="w-3.5 h-3.5 text-led-blue" />
              )}
              <span>Test Ping</span>
            </button>
          </div>
        </div>

        {/* Test Result Message */}
        {testStatus !== 'idle' && (
          <div
            className={`p-3 rounded-xl border text-xs font-mono flex items-start gap-2 ${
              testStatus === 'success'
                ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
                : testStatus === 'error'
                ? 'bg-red-950/40 text-red-300 border-red-500/30'
                : 'bg-graphite-950 text-graphite-400 border-white/5'
            }`}
          >
            {testStatus === 'success' ? (
              <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : testStatus === 'error' ? (
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            ) : (
              <RefreshCw className="w-4 h-4 text-led-blue shrink-0 mt-0.5 animate-spin" />
            )}
            <span className="leading-relaxed">{testMessage}</span>
          </div>
        )}

        {/* Default Config Values */}
        <div className="p-3.5 rounded-xl bg-graphite-950 border border-white/5 space-y-1.5 text-xs font-mono text-graphite-400">
          <div className="flex justify-between">
            <span>Default Endpoint:</span>
            <span className="text-graphite-200">/api/telemetry</span>
          </div>
          <div className="flex justify-between">
            <span>Polling Interval:</span>
            <span className="text-graphite-200">3,000 ms</span>
          </div>
          <div className="flex justify-between">
            <span>Request Timeout:</span>
            <span className="text-graphite-200">4,000 ms</span>
          </div>
          <div className="flex justify-between">
            <span>Stale Threshold:</span>
            <span className="text-graphite-200">&gt; 30,000 ms</span>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-mono bg-led-blue text-graphite-950 font-semibold hover:bg-sky-300 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
