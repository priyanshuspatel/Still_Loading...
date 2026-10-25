import React, { useState, useEffect } from 'react';
import {
  RefreshCw,
  Radio,
  Battery,
  BatteryCharging,
  Download,
  AlertTriangle,
  Clock,
  Trash2,
  Sliders,
  Settings,
  ExternalLink,
} from 'lucide-react';
import { LEDMatrix } from './LEDMatrix';
import {
  TelemetrySnapshot,
  ActivityEvent,
  HardwareLightState,
} from '../types/telemetry';
import { DEMO_PRESETS, DemoPreset } from '../lib/demoData';
import {
  fetchLiveSnapshot,
  formatBytes,
  formatTransferSpeed,
  formatRelativeTime,
  DEFAULT_TELEMETRY_CONFIG,
} from '../lib/telemetryClient';

interface LiveDashboardProps {
  isLiveMode: boolean;
  setIsLiveMode: (live: boolean) => void;
  onOpenSettingsModal: () => void;
}

export const LiveDashboard: React.FC<LiveDashboardProps> = ({
  isLiveMode,
  setIsLiveMode,
  onOpenSettingsModal,
}) => {
  // Active demo preset when in demo mode
  const [selectedPresetId, setSelectedPresetId] = useState<string>('download_active');
  const activePreset: DemoPreset =
    DEMO_PRESETS.find((p) => p.id === selectedPresetId) || DEMO_PRESETS[0];

  // Live state
  const [liveSnapshot, setLiveSnapshot] = useState<TelemetrySnapshot | null>(null);
  const [liveEvents, setLiveEvents] = useState<ActivityEvent[]>([]);
  const [isPolling, setIsPolling] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Manual matrix audition override
  const [manualStateOverride, setManualStateOverride] = useState<HardwareLightState | null>(null);
  const [manualProgressOverride, setManualProgressOverride] = useState<number | null>(null);

  // Poll live telemetry when isLiveMode is active
  useEffect(() => {
    if (!isLiveMode || !isPolling) return;

    let isMounted = true;
    const fetchTelemetry = async () => {
      try {
        setIsRefreshing(true);
        const snapshot = await fetchLiveSnapshot(
          DEFAULT_TELEMETRY_CONFIG.endpointUrl,
          DEFAULT_TELEMETRY_CONFIG.timeoutMs
        );
        if (isMounted) {
          setLiveSnapshot(snapshot);
          setConnectionError(null);

          // Push event if state changed
          const newEvent: ActivityEvent = {
            id: `live-${Date.now()}`,
            timestamp: Date.now(),
            type: snapshot.lights.state === 'download' ? 'download' : 'battery',
            title: `Polled State: ${snapshot.lights.state.toUpperCase()}`,
            detail: `Battery: ${snapshot.battery.percent ?? '--'}% | Progress: ${snapshot.lights.progress}%`,
            badgeText: 'Live Stream',
            severity: 'info',
            is_demo: false,
          };
          setLiveEvents((prev) => [newEvent, ...prev.slice(0, 19)]);
        }
      } catch (err: any) {
        if (isMounted) {
          setConnectionError(err.message || 'Unable to connect to telemetry service');
          if (liveSnapshot) {
            setLiveSnapshot({
              ...liveSnapshot,
              is_stale: true,
              connection: {
                ...liveSnapshot.connection,
                dataService: 'offline',
              },
            });
          }
        }
      } finally {
        if (isMounted) setIsRefreshing(false);
      }
    };

    fetchTelemetry();
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchTelemetry();
      }
    }, DEFAULT_TELEMETRY_CONFIG.pollIntervalMs);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isLiveMode, isPolling]);

  // Active snapshot resolution
  const currentSnapshot: TelemetrySnapshot = isLiveMode && liveSnapshot
    ? liveSnapshot
    : activePreset.snapshot;

  const currentEvents: ActivityEvent[] = isLiveMode
    ? liveEvents
    : activePreset.events;

  const currentMatrixState: HardwareLightState =
    manualStateOverride ?? currentSnapshot.lights.state;
  const currentMatrixProgress: number =
    manualProgressOverride ?? currentSnapshot.lights.progress;

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    if (isLiveMode) {
      try {
        const snapshot = await fetchLiveSnapshot(DEFAULT_TELEMETRY_CONFIG.endpointUrl);
        setLiveSnapshot(snapshot);
        setConnectionError(null);
      } catch (err: any) {
        setConnectionError(err.message);
      } finally {
        setIsRefreshing(false);
      }
    } else {
      // In demo mode, refresh animates and resets timestamps
      setTimeout(() => {
        setIsRefreshing(false);
      }, 400);
    }
  };

  const handleClearEvents = () => {
    if (window.confirm('Clear session activity log?')) {
      if (isLiveMode) {
        setLiveEvents([]);
      }
    }
  };

  const resetManualOverride = () => {
    setManualStateOverride(null);
    setManualProgressOverride(null);
  };

  return (
    <section className="py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-8">
      {/* 1. Header Bar: Title, Live/Demo Status, Polling Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-graphite-900/90 border border-white/10 shadow-panel backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Live Dashboard
            </h1>

            {/* Genuine Status Badge */}
            {isLiveMode ? (
              connectionError ? (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-red-500/20 text-red-400 border border-red-500/40">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  OFFLINE / UNREACHABLE
                </span>
              ) : currentSnapshot.is_stale ? (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  STALE TELEMETRY
                </span>
              ) : (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-led-blue/20 text-led-blue border border-led-blue/40 shadow-led-glow">
                  <span className="w-2 h-2 rounded-full bg-led-blue animate-pulse" />
                  LIVE CONNECTED
                </span>
              )
            ) : (
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-accent-lime/20 text-accent-lime border border-accent-lime/40">
                <span className="w-2 h-2 rounded-full bg-accent-lime" />
                SIMULATED DEMO
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-graphite-400 font-mono">
            Source: <span className="text-graphite-200">{currentSnapshot.source_label}</span> •{' '}
            Priority Mode: <span className="text-accent-lime font-medium uppercase">{currentSnapshot.lights.display_mode}</span> •{' '}
            Updated: <span className="text-graphite-300">{formatRelativeTime(currentSnapshot.timestamp)}</span>
          </p>
        </div>

        {/* Dashboard Top Right Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Demo / Live Mode Selector */}
          <div className="flex items-center bg-graphite-950 p-1 rounded-xl border border-white/10 text-xs font-mono">
            <button
              onClick={() => {
                setIsLiveMode(false);
                resetManualOverride();
              }}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                !isLiveMode
                  ? 'bg-accent-lime/20 text-accent-lime font-bold border border-accent-lime/30'
                  : 'text-graphite-400 hover:text-white'
              }`}
            >
              Demo Mode
            </button>
            <button
              onClick={() => {
                setIsLiveMode(true);
                resetManualOverride();
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                isLiveMode
                  ? 'bg-led-blue/20 text-led-blue font-bold border border-led-blue/30 shadow-sm'
                  : 'text-graphite-400 hover:text-white'
              }`}
            >
              <Radio className="w-3 h-3" />
              <span>Live Feed</span>
            </button>
          </div>

          {/* Refresh Action */}
          <button
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-mono bg-graphite-800 hover:bg-graphite-700 text-graphite-200 border border-white/10 disabled:opacity-50"
            title="Poll telemetry endpoint now"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-led-blue' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          {/* Polling Toggle */}
          {isLiveMode && (
            <button
              onClick={() => setIsPolling(!isPolling)}
              className={`px-3 py-2 rounded-xl text-xs font-mono border transition-all ${
                isPolling
                  ? 'bg-graphite-800 text-graphite-200 border-white/10'
                  : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
              }`}
            >
              {isPolling ? 'Polling: 3s' : 'Polling: Paused'}
            </button>
          )}

          {/* Config Settings */}
          <button
            onClick={onOpenSettingsModal}
            className="p-2 rounded-xl bg-graphite-800 hover:bg-graphite-700 text-graphite-400 hover:text-white border border-white/10"
            title="Configure Live Telemetry Gateway URL"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Connection Notice / Warning Banner if Offline or Error */}
      {isLiveMode && connectionError && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-500/30 text-red-200 text-xs font-mono flex items-start justify-between gap-3 animate-in fade-in">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-red-300">Live Telemetry Gateway Unreachable</div>
              <p className="text-red-400/90 mt-0.5">
                {connectionError}. Make sure the telemetry relay or receiver (192.168.1.5:8090) is running, or switch to Demo Mode.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsLiveMode(false)}
            className="px-3 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 shrink-0 font-medium"
          >
            Switch to Demo
          </button>
        </div>
      )}

      {/* Demo Scenario Selector (Shown in Demo Mode) */}
      {!isLiveMode && (
        <div className="p-4 rounded-xl bg-graphite-900/60 border border-white/[0.08]">
          <div className="flex items-center justify-between text-xs font-mono text-graphite-400 mb-2.5">
            <span className="flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-accent-lime" />
              <span className="font-semibold text-graphite-200">Select Demo Scenario:</span>
            </span>
            <span className="text-[10px] text-graphite-500">Deterministic Hardware Scenarios</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2">
            {DEMO_PRESETS.map((p) => {
              const selected = selectedPresetId === p.id && manualStateOverride === null;
              return (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedPresetId(p.id);
                    resetManualOverride();
                  }}
                  className={`text-left p-2.5 rounded-lg border text-xs font-mono transition-all truncate ${
                    selected
                      ? 'bg-accent-lime/15 text-accent-lime border-accent-lime/40 font-semibold shadow-sm'
                      : 'bg-graphite-800/60 text-graphite-400 hover:text-graphite-200 hover:bg-graphite-800 border-white/5'
                  }`}
                  title={p.description}
                >
                  <div className="truncate">{p.name.split(' ')[0]} {p.name.split(' ')[1]}</div>
                  <div className="text-[10px] text-graphite-500 uppercase">{p.category}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. Primary Telemetry Monitors: Battery & Chrome Download */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Battery Monitor Card */}
        <div className="p-6 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel relative flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/[0.08]">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-accent-lime/10 text-accent-lime border border-accent-lime/20">
                  {currentSnapshot.battery.charging_state === 'charging' ? (
                    <BatteryCharging className="w-5 h-5 animate-pulse" />
                  ) : (
                    <Battery className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">MacBook Battery Gauge</h3>
                  <span className="text-[11px] font-mono text-graphite-400">
                    Source: {currentSnapshot.battery.source ?? 'pmset -g batt'}
                  </span>
                </div>
              </div>

              {/* Status Pill */}
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono uppercase font-semibold border ${
                  currentSnapshot.battery.charging_state === 'charging'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : currentSnapshot.battery.charging_state === 'full'
                    ? 'bg-accent-lime/20 text-accent-lime border-accent-lime/40'
                    : 'bg-graphite-800 text-graphite-300 border-white/10'
                }`}
              >
                {currentSnapshot.battery.charging_state}
              </span>
            </div>

            {/* Main Percentage Display */}
            <div className="flex items-baseline gap-3 my-2">
              <span className="text-5xl sm:text-6xl font-bold font-mono tracking-tight text-white">
                {currentSnapshot.battery.percent !== null ? `${currentSnapshot.battery.percent}%` : '--'}
              </span>
              <span className="text-xs font-mono text-graphite-400">
                {currentSnapshot.battery.charging_state === 'charging'
                  ? '⚡ AC Power Connected'
                  : currentSnapshot.battery.percent === 100
                  ? 'Charged'
                  : 'On Battery Power'}
              </span>
            </div>

            {/* Visual Battery Bar */}
            <div className="w-full bg-graphite-950 rounded-full h-3 p-0.5 border border-white/10 my-4 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  currentSnapshot.battery.charging_state === 'charging'
                    ? 'bg-gradient-to-r from-emerald-500 to-accent-lime'
                    : (currentSnapshot.battery.percent ?? 0) <= 20
                    ? 'bg-red-500'
                    : 'bg-led-blue'
                }`}
                style={{ width: `${Math.max(4, currentSnapshot.battery.percent ?? 0)}%` }}
              />
            </div>
          </div>

          <div className="pt-3 border-t border-white/[0.06] text-xs font-mono text-graphite-400 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-graphite-500" />
              <span>Interval: 15s poll • 5m refresh</span>
            </span>
            <span className="text-graphite-500">Sleep: Pauses on lid close</span>
          </div>
        </div>

        {/* Chrome Download Monitor Card */}
        <div className="p-6 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel relative flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/[0.08]">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-led-blue/10 text-led-blue border border-led-blue/20">
                  <Download className={`w-5 h-5 ${currentSnapshot.download.active ? 'animate-bounce' : ''}`} />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">Chrome Download Monitor</h3>
                  <span className="text-[11px] font-mono text-graphite-400">
                    File: {currentSnapshot.download.filename_display ?? 'No active downloads'}
                  </span>
                </div>
              </div>

              {/* Status Pill */}
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono uppercase font-semibold border ${
                  currentSnapshot.download.state === 'downloading'
                    ? 'bg-led-blue/20 text-led-blue border-led-blue/40 shadow-sm'
                    : currentSnapshot.download.state === 'completed'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-graphite-800 text-graphite-400 border-white/10'
                }`}
              >
                {currentSnapshot.download.state}
              </span>
            </div>

            {/* Main Percentage Display */}
            <div className="flex items-baseline gap-3 my-2">
              <span className="text-5xl sm:text-6xl font-bold font-mono tracking-tight text-white">
                {currentSnapshot.download.progress_known
                  ? `${currentSnapshot.download.progress}%`
                  : currentSnapshot.download.active
                  ? '...'
                  : '0%'}
              </span>
              <span className="text-xs font-mono text-graphite-400">
                {currentSnapshot.download.active
                  ? `${formatBytes(currentSnapshot.download.downloaded_bytes)} of ${
                      currentSnapshot.download.total_bytes
                        ? formatBytes(currentSnapshot.download.total_bytes)
                        : 'unknown'
                    }`
                  : 'Monitoring .crdownload streams'}
              </span>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-graphite-950 rounded-full h-3 p-0.5 border border-white/10 my-4 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-500 to-led-blue transition-all duration-300"
                style={{ width: `${Math.max(0, currentSnapshot.download.progress)}%` }}
              />
            </div>
          </div>

          <div className="pt-3 border-t border-white/[0.06] text-xs font-mono text-graphite-400 flex items-center justify-between">
            <span>Transfer Speed: {formatTransferSpeed(currentSnapshot.download.speed_bytes_sec)}</span>
            <span className="text-graphite-500">Auto Priority: Active downloads win</span>
          </div>
        </div>
      </div>

      {/* 3. Physical Matrix Preview & Interactive State Audition */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: LED Matrix Card */}
        <div className="lg:col-span-7 p-6 sm:p-8 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel flex flex-col items-center">
          <div className="w-full flex items-center justify-between mb-6 pb-3 border-b border-white/[0.08]">
            <div>
              <h3 className="text-lg font-semibold text-white">
                Physical Matrix Twin (8 × 13)
              </h3>
              <p className="text-xs font-mono text-graphite-400">
                Pixel-perfect reproduction of STM32 matrix firmware
              </p>
            </div>
            {manualStateOverride && (
              <button
                onClick={resetManualOverride}
                className="px-2.5 py-1 rounded text-xs font-mono bg-white/10 text-graphite-200 hover:bg-white/20"
              >
                Reset to Telemetry
              </button>
            )}
          </div>

          {/* Real 8x13 Matrix */}
          <LEDMatrix
            state={currentMatrixState}
            progress={currentMatrixProgress}
            progressKnown={currentSnapshot.lights.progress_known}
            size="lg"
            showLabels={true}
            showLed3={true}
            interactive={true}
            className="my-2"
          />

          {/* Matrix Interactive Audition Selector */}
          <div className="w-full mt-6 pt-4 border-t border-white/[0.08] text-xs font-mono">
            <div className="text-graphite-400 mb-2 font-medium">
              Audition Physical Matrix Patterns:
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { label: 'Idle Dots (...)', state: 'idle', prog: 0 },
                { label: 'Job Running 38%', state: 'running', prog: 38 },
                { label: 'Slow 64%', state: 'slow', prog: 64 },
                { label: 'Stall Alert [ ! ]', state: 'suspected_stall', prog: 42 },
                { label: 'Job 100% Check', state: 'completed', prog: 100 },
                { label: 'Failed (X)', state: 'failed', prog: 15 },
                { label: 'Battery 82%', state: 'battery', prog: 82 },
                { label: 'Unavailable (--)', state: 'battery_unavailable', prog: 0 },
              ].map((btn) => (
                <button
                  key={btn.label}
                  onClick={() => {
                    setManualStateOverride(btn.state as HardwareLightState);
                    setManualProgressOverride(btn.prog);
                  }}
                  className={`p-2 rounded-lg border text-left truncate transition-colors ${
                    manualStateOverride === btn.state
                      ? 'bg-led-blue/20 text-led-blue border-led-blue/40 font-semibold'
                      : 'bg-graphite-800/60 text-graphite-300 hover:text-white border-white/5'
                  }`}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Connection Matrix & Diagnostics */}
        <div className="lg:col-span-5 space-y-6">
          {/* Connection Hierarchy Card */}
          <div className="p-6 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <h3 className="text-base font-semibold text-white">System Connectivity</h3>
              <span className="text-xs font-mono text-graphite-400">Telemetry Health</span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              {/* Web Gateway */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-graphite-950 border border-white/5">
                <div>
                  <div className="text-white font-medium">stillloading.tech Web Service</div>
                  <div className="text-graphite-500 text-[11px]">Public Read-Only Endpoint</div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                    currentSnapshot.connection.dataService === 'online'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-red-500/20 text-red-300 border border-red-500/30'
                  }`}
                >
                  {currentSnapshot.connection.dataService.toUpperCase()}
                </span>
              </div>

              {/* Mac Monitoring Agent */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-graphite-950 border border-white/5">
                <div>
                  <div className="text-white font-medium">macOS Monitoring Agent</div>
                  <div className="text-graphite-500 text-[11px]">pmset + Chrome Observer</div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                    currentSnapshot.connection.macAgent === 'active'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : currentSnapshot.connection.macAgent === 'stale'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'bg-graphite-800 text-graphite-400 border border-white/10'
                  }`}
                >
                  {currentSnapshot.connection.macAgent.toUpperCase()}
                </span>
              </div>

              {/* UNO Q Receiver */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-graphite-950 border border-white/5">
                <div>
                  <div className="text-white font-medium">UNO Q Receiver (Port 8090)</div>
                  <div className="text-graphite-500 text-[11px]">Qualcomm QRB2210 Debian Linux</div>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {currentSnapshot.connection.receiver.toUpperCase()}
                </span>
              </div>

              {/* Physical LED Matrix */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-graphite-950 border border-white/5">
                <div>
                  <div className="text-white font-medium">STM32 8×13 LED Hardware</div>
                  <div className="text-graphite-500 text-[11px]">Bridge set_job_lights</div>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-led-blue/20 text-led-blue border border-led-blue/30">
                  {currentSnapshot.connection.matrixHardware.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] text-[11px] text-graphite-400 leading-relaxed">
              <strong>Honest Connectivity Rule:</strong> A successful response from the web service does not automatically guarantee physical hardware is plugged into your desk. Disconnected components are reported explicitly.
            </div>
          </div>
        </div>
      </div>

      {/* 4. Activity Event Timeline */}
      <div className="p-6 sm:p-8 rounded-2xl bg-graphite-900/80 border border-white/10 shadow-panel">
        <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/[0.08]">
          <div>
            <h3 className="text-lg font-semibold text-white">Activity Timeline</h3>
            <p className="text-xs font-mono text-graphite-400">
              Chronological log of verified hardware & telemetry changes
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClearEvents}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-graphite-800 text-graphite-400 hover:text-red-400 hover:bg-graphite-700 border border-white/10"
              title="Clear session events"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Log</span>
            </button>
          </div>
        </div>

        {currentEvents.length === 0 ? (
          <div className="py-12 text-center text-graphite-500 font-mono text-xs">
            No events recorded in this session yet. Events will appear as telemetry arrives.
          </div>
        ) : (
          <div className="space-y-3 font-mono text-xs">
            {currentEvents.map((evt) => (
              <div
                key={evt.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-xl bg-graphite-950 border border-white/5 hover:border-white/10 transition-colors gap-2"
              >
                <div className="flex items-start sm:items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase shrink-0 ${
                      evt.severity === 'success'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : evt.severity === 'warning'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : evt.severity === 'error'
                        ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                        : 'bg-led-blue/20 text-led-blue border border-led-blue/30'
                    }`}
                  >
                    {evt.badgeText}
                  </span>
                  <div>
                    <span className="font-medium text-white">{evt.title}</span>
                    <span className="text-graphite-400 text-[11px] block sm:inline sm:ml-2">
                      — {evt.detail}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[11px] text-graphite-500 shrink-0 self-end sm:self-center">
                  {evt.is_demo && (
                    <span className="px-1.5 py-0.2 rounded bg-accent-lime/10 text-accent-lime text-[9px] border border-accent-lime/20 font-bold">
                      DEMO
                    </span>
                  )}
                  <span>{formatRelativeTime(evt.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
