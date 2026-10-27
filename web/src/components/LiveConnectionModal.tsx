import React, { useState } from 'react';
import { X, ShieldCheck, Radio, Check, AlertCircle, RefreshCw } from 'lucide-react';
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
    setTestMessage('Pinging telemetry relay endpoint...');
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
      setTestMessage(
        err.message || 'Unable to reach endpoint. Verify telemetry_relay.py is running on port 8765.'
      );
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="relative w-full max-w-lg p-6 rounded-xl bg-white dark:bg-[#181B20] border border-black/10 dark:border-white/10 shadow-2xl space-y-5">
        <div className="flex items-center justify-between pb-3.5 border-b border-black/[0.08] dark:border-white/10">
          <div>
            <h3 id="modal-title" className="text-base font-extrabold text-[#141517] dark:text-white">
              Live Telemetry Relay Configuration
            </h3>
            <p className="text-xs font-mono text-[#787C82]">
              Read-only sanitized telemetry gateway
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#787C82] hover:text-[#141517] dark:hover:text-white"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-3.5 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] text-xs space-y-1">
          <div className="flex items-center gap-2 text-[#141517] dark:text-white font-bold">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Zero Exposed Credentials in Browser</span>
          </div>
          <p className="text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
            Shared bearer tokens and private board IPs (<code className="font-mono">192.168.1.5</code>) remain strictly on your Mac and relay server.
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="block text-xs font-mono text-[#4A4D52] dark:text-[#9CA3AF] font-semibold">
            TELEMETRY RELAY ENDPOINT URL:
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="http://127.0.0.1:8765/api/telemetry"
              className="w-full px-3 py-2 rounded-lg bg-[#F9F9F8] dark:bg-[#0C0D0F] border border-black/10 dark:border-white/10 text-[#141517] dark:text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[#0055FF]"
            />
            <button
              onClick={handleTestConnection}
              disabled={testStatus === 'testing'}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#141517] hover:bg-[#0055FF] text-white text-xs font-mono font-semibold disabled:opacity-50 shrink-0 transition-colors"
            >
              {testStatus === 'testing' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Radio className="w-3.5 h-3.5" />
              )}
              <span>Ping</span>
            </button>
          </div>
        </div>

        {testStatus !== 'idle' && (
          <div
            className={`p-3 rounded-lg text-xs font-mono flex items-start gap-2 ${
              testStatus === 'success'
                ? 'bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
                : testStatus === 'error'
                ? 'bg-red-500/10 text-red-800 dark:text-red-300'
                : 'bg-[#F1F0EC] text-[#4A4D52]'
            }`}
          >
            {testStatus === 'success' ? (
              <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : testStatus === 'error' ? (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            ) : (
              <RefreshCw className="w-4 h-4 text-[#0055FF] shrink-0 mt-0.5 animate-spin" />
            )}
            <span className="leading-relaxed">{testMessage}</span>
          </div>
        )}

        <div className="flex items-center justify-end pt-3 border-t border-black/[0.08] dark:border-white/10">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-[#141517] hover:bg-[#0055FF] text-white transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
