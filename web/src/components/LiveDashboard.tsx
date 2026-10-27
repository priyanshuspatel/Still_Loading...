import React, { useState, useEffect, useRef } from 'react';
import {
  RefreshCw,
  Radio,
  AlertTriangle,
  Trash2,
  Settings,
  Copy,
  Check,
  Volume2,
  VolumeX,
  Grid,
  Sparkles,
} from 'lucide-react';
import { audioCues } from '../lib/audioCues';
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
import {
  emptyFrame,
  MatrixFrame,
  renderHeartFrame,
  renderCompletedCheckFrame,
  renderStallFrame,
} from '../lib/matrixEngine';
import { gemmaCardModel } from '../lib/gemmaCard';
import { GemmaAnalysisCard } from './GemmaAnalysisCard';

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
  const [selectedPresetId, setSelectedPresetId] = useState<string>('download_active');
  const activePreset: DemoPreset =
    DEMO_PRESETS.find((p) => p.id === selectedPresetId) || DEMO_PRESETS[0];

  const [liveSnapshot, setLiveSnapshot] = useState<TelemetrySnapshot | null>(null);
  const [liveEvents, setLiveEvents] = useState<ActivityEvent[]>([]);
  const [isPolling, setIsPolling] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const [manualStateOverride, setManualStateOverride] = useState<HardwareLightState | null>(null);
  const [manualProgressOverride, setManualProgressOverride] = useState<number | null>(null);
  const [copiedFix, setCopiedFix] = useState(false);

  const [workbenchTab, setWorkbenchTab] = useState<'firmware' | 'painter'>('firmware');
  const [customFrame, setCustomFrame] = useState<MatrixFrame>(() => renderHeartFrame(6, 75));
  const [brushLevel, setBrushLevel] = useState<number>(7);
  const [copiedBitmap, setCopiedBitmap] = useState<boolean>(false);

  const [audioEnabled, setAudioEnabled] = useState<boolean>(false);
  const prevLightStateRef = useRef<HardwareLightState | null>(null);

  const handleCopyFix = (text: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedFix(true);
      setTimeout(() => setCopiedFix(false), 2000);
    }
  };

  useEffect(() => {
    if (!audioEnabled || !isLiveMode || !liveSnapshot) return;
    const newState = liveSnapshot.lights.state;
    const prevState = prevLightStateRef.current;
    if (prevState !== null && prevState !== newState) {
      if (newState === 'completed') audioCues.playCompleted();
      else if (newState === 'failed') audioCues.playFailed();
      else if (newState === 'suspected_stall') audioCues.playStall();
    }
    prevLightStateRef.current = newState;
  }, [liveSnapshot, audioEnabled, isLiveMode]);

  const handleAudioToggle = () => {
    const next = audioCues.toggle();
    setAudioEnabled(next);
  };

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

          const newEvent: ActivityEvent = {
            id: `live-${Date.now()}`,
            timestamp: Date.now(),
            type: snapshot.lights.state === 'download' ? 'download' : 'battery',
            title: `State: ${snapshot.lights.state.toUpperCase()}`,
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

  const currentSnapshot: TelemetrySnapshot =
    isLiveMode && liveSnapshot ? liveSnapshot : activePreset.snapshot;

  const currentEvents: ActivityEvent[] = isLiveMode
    ? liveEvents
    : activePreset.events;

  const currentMatrixState: HardwareLightState =
    manualStateOverride ?? currentSnapshot.lights.state;
  const gemmaAnalysis = gemmaCardModel(
    currentSnapshot.job?.explanation,
    currentSnapshot.job?.is_failure || currentMatrixState === 'failed'
      ? 'failed'
      : currentMatrixState
  );
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
      setTimeout(() => {
        setIsRefreshing(false);
      }, 350);
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
    setWorkbenchTab('firmware');
  };

  const handlePixelPaint = (row: number, col: number) => {
    setWorkbenchTab('painter');
    setCustomFrame((prev) => {
      const next = prev.map((r) => [...r]);
      next[row][col] = next[row][col] === brushLevel ? 0 : brushLevel;
      return next;
    });
  };

  const handleCopyFrameCode = () => {
    const formatted =
      '[\n' +
      customFrame.map((row) => `  [${row.join(', ')}]`).join(',\n') +
      '\n]';
    if (navigator.clipboard) {
      navigator.clipboard.writeText(formatted);
      setCopiedBitmap(true);
      setTimeout(() => setCopiedBitmap(false), 2000);
    }
  };

  // 20-segment discrete hardware meter helper
  const renderSegmentedBar = (percent: number, activeColorClass: string) => {
    const litSegments = Math.round((Math.max(0, Math.min(100, percent)) / 100) * 20);
    return (
      <div className="grid grid-cols-20 gap-1 my-3" style={{ gridTemplateColumns: 'repeat(20, minmax(0, 1fr))' }}>
        {Array.from({ length: 20 }).map((_, idx) => (
          <div
            key={idx}
            className={`h-2.5 rounded-[2px] transition-colors duration-200 ${
              idx < litSegments
                ? activeColorClass
                : 'bg-black/[0.07] dark:bg-white/[0.08]'
            }`}
          />
        ))}
      </div>
    );
  };

  return (
    <section className="py-6 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-6">
      {/* Unified Architectural Telemetry Console (Zero Bubbly Cards) */}
      <div className="arch-grid">
        {/* Top Console Bar */}
        <div className="arch-cell p-5 sm:px-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-[#141517] dark:text-white">
                Telemetry Control Deck
              </h1>

              {isLiveMode ? (
                connectionError ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-mono font-semibold bg-red-500/15 text-red-700 dark:text-red-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-600" />
                    OFFLINE
                  </span>
                ) : currentSnapshot.is_stale ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-mono font-semibold bg-amber-500/15 text-amber-800 dark:text-amber-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    STALE
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-mono font-semibold bg-[#0055FF]/10 text-[#0055FF] dark:text-[#38BDF8]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0055FF] dark:bg-[#38BDF8] animate-pulse" />
                    LIVE STREAM
                  </span>
                )
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-mono font-semibold bg-emerald-500/15 text-emerald-800 dark:text-emerald-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                  SIMULATED
                </span>
              )}
            </div>
            <p className="text-xs font-mono text-[#787C82]">
              Source: <strong className="text-[#141517] dark:text-white">{currentSnapshot.source_label}</strong> •{' '}
              Priority: <strong className="text-[#0055FF] dark:text-[#38BDF8] uppercase">{currentSnapshot.lights.display_mode}</strong> •{' '}
              Sync: <strong className="text-[#4A4D52] dark:text-slate-300">{formatRelativeTime(currentSnapshot.timestamp)}</strong>
            </p>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center bg-[#F1F0EC] dark:bg-white/[0.06] p-0.5 rounded-lg text-xs font-semibold">
              <button
                onClick={() => {
                  setIsLiveMode(false);
                  resetManualOverride();
                }}
                className={`px-3 py-1.5 rounded-md transition-all ${
                  !isLiveMode
                    ? 'bg-white dark:bg-[#252830] text-[#141517] dark:text-white shadow-sm'
                    : 'text-[#787C82]'
                }`}
              >
                Demo
              </button>
              <button
                onClick={() => {
                  setIsLiveMode(true);
                  resetManualOverride();
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                  isLiveMode
                    ? 'bg-[#0055FF] text-white shadow-sm'
                    : 'text-[#787C82]'
                }`}
              >
                <Radio className="w-3 h-3" />
                <span>Live</span>
              </button>
            </div>

            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#F1F0EC] hover:bg-[#E5E3DC] dark:bg-white/[0.06] text-[#141517] dark:text-white disabled:opacity-50 transition-colors"
              title="Poll telemetry endpoint now"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#0055FF]' : ''}`} />
              <span>Sync</span>
            </button>

            {isLiveMode && (
              <button
                onClick={() => setIsPolling(!isPolling)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isPolling
                    ? 'bg-[#F1F0EC] dark:bg-white/[0.06] text-[#141517] dark:text-white'
                    : 'bg-amber-500/15 text-amber-800 dark:text-amber-300'
                }`}
              >
                {isPolling ? '3s Poll' : 'Paused'}
              </button>
            )}

            <button
              onClick={handleAudioToggle}
              className={`p-2 rounded-lg transition-all ${
                audioEnabled
                  ? 'bg-[#0055FF]/15 text-[#0055FF] dark:text-[#38BDF8]'
                  : 'bg-[#F1F0EC] dark:bg-white/[0.06] text-[#4A4D52] dark:text-[#9CA3AF]'
              }`}
              title={audioEnabled ? 'Audio Chimes Enabled' : 'Enable Audio Chimes'}
              aria-label={audioEnabled ? 'Mute audio cues' : 'Enable audio cues'}
            >
              {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>

            <button
              onClick={onOpenSettingsModal}
              className="p-2 rounded-lg bg-[#F1F0EC] dark:bg-white/[0.06] text-[#4A4D52] dark:text-[#9CA3AF] hover:text-[#141517] dark:hover:text-white transition-colors"
              title="Configure Telemetry Gateway URL"
              aria-label="Configure Telemetry Gateway URL"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Inline Scenario Strip (Demo Mode) */}
        {!isLiveMode && (
          <div className="arch-cell-stone px-5 py-3 flex items-center gap-2 overflow-x-auto">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#787C82] shrink-0 mr-1">
              Scenario:
            </span>
            {DEMO_PRESETS.map((p) => {
              const selected =
                selectedPresetId === p.id &&
                manualStateOverride === null &&
                workbenchTab === 'firmware';
              return (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedPresetId(p.id);
                    resetManualOverride();
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 transition-all ${
                    selected
                      ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517] shadow-sm'
                      : 'bg-white dark:bg-[#181B20] text-[#4A4D52] dark:text-[#9CA3AF] hover:text-[#141517] dark:hover:text-white border border-black/[0.06] dark:border-white/10'
                  }`}
                >
                  {p.name.split(' ')[0]} {p.name.split(' ')[1]}
                </button>
              );
            })}
          </div>
        )}

        {/* Offline Error Banner */}
        {isLiveMode && connectionError && (
          <div className="arch-cell p-4 bg-red-500/10 text-red-900 dark:text-red-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Live Gateway Unreachable: </span>
                <span>{connectionError}. Start relay/telemetry_relay.py or switch to Simulated Demo.</span>
              </div>
            </div>
            <button
              onClick={() => setIsLiveMode(false)}
              className="px-3 py-1 rounded-md bg-red-600 text-white font-semibold shrink-0 self-start sm:self-auto"
            >
              Use Demo
            </button>
          </div>
        )}

        {/* Main Console Split: Left 8x13 Matrix Workbench (7 cols) + Right Telemetry Readouts (5 cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-[1px] bg-black/[0.08] dark:bg-white/[0.08]">
          {/* Left: 8x13 Optical Matrix Workbench */}
          <div className="lg:col-span-7 arch-cell-stone p-5 sm:p-7 flex flex-col items-center justify-between">
            <div className="w-full flex flex-wrap items-center justify-between gap-2 mb-5">
              <div>
                <h2 className="text-base font-bold text-[#141517] dark:text-white">
                  8×13 Optical Matrix Workbench
                </h2>
                <p className="text-xs text-[#787C82]">
                  {workbenchTab === 'firmware'
                    ? '1:1 STM32U585 firmware state machine & progress fader'
                    : '3-bit (L0–L7) custom bitmap composer — click LEDs to paint'}
                </p>
              </div>

              <div className="flex items-center bg-white dark:bg-[#181B20] p-0.5 rounded-lg border border-black/[0.08] dark:border-white/10 text-xs font-semibold">
                <button
                  onClick={() => setWorkbenchTab('firmware')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all ${
                    workbenchTab === 'firmware'
                      ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517]'
                      : 'text-[#787C82]'
                  }`}
                >
                  <Sparkles className="w-3 h-3" />
                  <span>Firmware</span>
                </button>
                <button
                  onClick={() => setWorkbenchTab('painter')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all ${
                    workbenchTab === 'painter'
                      ? 'bg-[#0055FF] text-white'
                      : 'text-[#787C82]'
                  }`}
                >
                  <Grid className="w-3 h-3" />
                  <span>Pixel Painter</span>
                </button>
              </div>
            </div>

            <LEDMatrix
              state={currentMatrixState}
              progress={currentMatrixProgress}
              progressKnown={currentSnapshot.lights.progress_known}
              manualFrame={workbenchTab === 'painter' ? customFrame : null}
              onPixelClick={handlePixelPaint}
              size="lg"
              showLabels={true}
              showLed3={true}
              interactive={true}
              className="w-full max-w-md my-1"
            />

            {workbenchTab === 'firmware' ? (
              <div className="w-full mt-5 pt-4 border-t border-black/[0.08] dark:border-white/10 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#4A4D52] dark:text-[#9CA3AF]">
                    Progress Override ({currentMatrixProgress}%)
                  </span>
                  {manualStateOverride && (
                    <button
                      onClick={resetManualOverride}
                      className="text-[#0055FF] dark:text-[#38BDF8] font-semibold underline"
                    >
                      Reset to Scenario
                    </button>
                  )}
                </div>

                <input
                  type="range"
                  min={0}
                  max={100}
                  value={currentMatrixProgress}
                  onChange={(e) => setManualProgressOverride(Number(e.target.value))}
                  aria-label="Matrix progress override slider"
                  className="w-full studio-fader"
                />

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1">
                  {[
                    { label: 'Idle Dots (...)', state: 'idle', prog: 0 },
                    { label: 'Running 38%', state: 'running', prog: 38 },
                    { label: 'Slow 64%', state: 'slow', prog: 64 },
                    { label: 'Stall [ ! ]', state: 'suspected_stall', prog: 42 },
                    { label: '100% Check', state: 'completed', prog: 100 },
                    { label: 'Failed (X)', state: 'failed', prog: 24 },
                    { label: 'Battery 82%', state: 'battery', prog: 82 },
                    { label: 'Unavailable (--)', state: 'battery_unavailable', prog: 0 },
                  ].map((btn) => {
                    const isSelected = currentMatrixState === btn.state;
                    return (
                      <button
                        key={btn.label}
                        onClick={() => {
                          setManualStateOverride(btn.state as HardwareLightState);
                          setManualProgressOverride(btn.prog);
                        }}
                        className={`p-2 rounded-lg text-left truncate transition-all font-medium ${
                          isSelected
                            ? 'bg-[#141517] text-white dark:bg-white dark:text-[#141517] font-semibold'
                            : 'bg-white dark:bg-[#181B20] text-[#4A4D52] dark:text-[#9CA3AF] border border-black/[0.06] dark:border-white/10'
                        }`}
                      >
                        {btn.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="w-full mt-5 pt-4 border-t border-black/[0.08] dark:border-white/10 space-y-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-[#4A4D52] dark:text-[#9CA3AF]">
                    3-Bit Brightness Brush:
                  </span>
                  <div className="flex items-center gap-1 font-mono">
                    {[0, 1, 2, 3, 4, 5, 6, 7].map((lvl) => (
                      <button
                        key={lvl}
                        onClick={() => setBrushLevel(lvl)}
                        className={`w-6 h-6 rounded-md font-bold transition-all ${
                          brushLevel === lvl
                            ? 'bg-[#0055FF] text-white'
                            : 'bg-white dark:bg-[#181B20] text-[#4A4D52] dark:text-[#9CA3AF] border border-black/[0.08]'
                        }`}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setCustomFrame(renderHeartFrame(6, 100))}
                      className="px-2.5 py-1 rounded-md bg-white dark:bg-[#181B20] border border-black/[0.08] text-[#141517] dark:text-white font-medium"
                    >
                      Heart
                    </button>
                    <button
                      onClick={() => setCustomFrame(renderCompletedCheckFrame())}
                      className="px-2.5 py-1 rounded-md bg-white dark:bg-[#181B20] border border-black/[0.08] text-[#141517] dark:text-white font-medium"
                    >
                      Check
                    </button>
                    <button
                      onClick={() => setCustomFrame(renderStallFrame(true, 50))}
                      className="px-2.5 py-1 rounded-md bg-white dark:bg-[#181B20] border border-black/[0.08] text-[#141517] dark:text-white font-medium"
                    >
                      [ ! ]
                    </button>
                    <button
                      onClick={() => setCustomFrame(emptyFrame())}
                      className="px-2.5 py-1 rounded-md bg-red-500/10 text-red-700 dark:text-red-300 font-medium"
                    >
                      Clear
                    </button>
                  </div>

                  <button
                    onClick={handleCopyFrameCode}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-md bg-[#141517] hover:bg-[#0055FF] text-white font-semibold transition-colors"
                  >
                    {copiedBitmap ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy Array</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right: Stacked Hairline Telemetry Readouts (Battery + Chrome + Connectivity) */}
          <div className="lg:col-span-5 arch-cell divide-y divide-black/[0.08] dark:divide-white/[0.08] flex flex-col justify-between">
            {/* Gauge 01: MacBook Battery */}
            <div className="p-5 sm:p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase tracking-wider text-[#787C82]">
                  01 // MACBOOK BATTERY ({currentSnapshot.battery.source ?? 'pmset'})
                </span>
                <span className="text-xs font-mono font-bold uppercase text-[#141517] dark:text-white">
                  {currentSnapshot.battery.charging_state}
                </span>
              </div>

              <div className="flex items-baseline justify-between">
                <span className="text-4xl font-extrabold font-mono tracking-tight text-[#141517] dark:text-white">
                  {currentSnapshot.battery.percent !== null
                    ? `${currentSnapshot.battery.percent}%`
                    : '--'}
                </span>
                <span className="text-xs text-[#787C82]">
                  {currentSnapshot.battery.charging_state === 'charging'
                    ? '⚡ MagSafe AC Power'
                    : '15s poll • 5m refresh'}
                </span>
              </div>

              {renderSegmentedBar(
                currentSnapshot.battery.percent ?? 0,
                currentSnapshot.battery.charging_state === 'charging'
                  ? 'bg-emerald-500'
                  : 'bg-[#141517] dark:bg-[#38BDF8]'
              )}
            </div>

            {/* Gauge 02: Chrome Download Stream */}
            <div className="p-5 sm:p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase tracking-wider text-[#787C82]">
                  02 // CHROME DOWNLOAD STREAM
                </span>
                <span className="text-xs font-mono font-bold uppercase text-[#0055FF] dark:text-[#38BDF8]">
                  {currentSnapshot.download.state}
                </span>
              </div>

              <div className="flex items-baseline justify-between">
                <span className="text-4xl font-extrabold font-mono tracking-tight text-[#141517] dark:text-white">
                  {currentSnapshot.download.progress_known
                    ? `${currentSnapshot.download.progress}%`
                    : currentSnapshot.download.active
                    ? '...'
                    : '0%'}
                </span>
                <span className="text-xs font-mono text-[#787C82]">
                  {formatTransferSpeed(currentSnapshot.download.speed_bytes_sec)}
                </span>
              </div>

              {renderSegmentedBar(
                currentSnapshot.download.progress,
                'bg-[#0055FF] dark:bg-[#38BDF8]'
              )}

              <div className="text-xs font-mono text-[#4A4D52] dark:text-[#9CA3AF] truncate">
                {currentSnapshot.download.active
                  ? `${currentSnapshot.download.filename_display} (${formatBytes(
                      currentSnapshot.download.downloaded_bytes
                    )})`
                  : 'No active .crdownload transfer'}
              </div>
            </div>

            {/* Gauge 03: 4-Node Connectivity */}
            <div className="p-5 sm:p-6 space-y-2.5">
              <div className="text-xs font-mono uppercase tracking-wider text-[#787C82]">
                03 // SYSTEM CONNECTIVITY CHAIN
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {[
                  {
                    label: 'Web Relay',
                    val: currentSnapshot.connection.dataService,
                    ok: currentSnapshot.connection.dataService === 'online',
                  },
                  {
                    label: 'macOS Agent',
                    val: currentSnapshot.connection.macAgent,
                    ok: currentSnapshot.connection.macAgent === 'active',
                  },
                  {
                    label: 'UNO Q :8090',
                    val: currentSnapshot.connection.receiver,
                    ok: currentSnapshot.connection.receiver === 'reachable',
                  },
                  {
                    label: 'STM32 Matrix',
                    val: currentSnapshot.connection.matrixHardware,
                    ok: true,
                  },
                ].map((n) => (
                  <div
                    key={n.label}
                    className="p-2.5 rounded-lg bg-[#F1F0EC] dark:bg-[#131519] flex items-center justify-between"
                  >
                    <span className="text-[#4A4D52] dark:text-[#9CA3AF]">
                      {n.label}
                    </span>
                    <span
                      className={`font-bold uppercase text-[10px] ${
                        n.ok
                          ? 'text-emerald-700 dark:text-emerald-400'
                          : 'text-amber-700 dark:text-amber-400'
                      }`}
                    >
                      {n.val}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Gemma analysis, or the rules failure card when Gemma did not run */}
        {gemmaAnalysis ? (
          <GemmaAnalysisCard model={gemmaAnalysis} />
        ) : (currentSnapshot.job?.is_failure ||
          currentMatrixState === 'failed' ||
          currentSnapshot.job?.explanation) && (
          <div className="arch-cell p-5 sm:p-6 bg-red-500/[0.03] space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase bg-red-600 text-white">
                  FAILURE INTELLIGENCE
                </span>
                <span className="font-bold text-sm text-[#141517] dark:text-white">
                  {currentSnapshot.job?.explanation?.summary ||
                    "Missing Python module: 'pandas'"}
                </span>
              </div>

              <button
                onClick={() =>
                  handleCopyFix(
                    currentSnapshot.job?.explanation?.suggestion ||
                      'pip install pandas'
                  )
                }
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-[#141517] hover:bg-[#0055FF] text-white transition-colors"
              >
                {copiedFix ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
                <span>
                  {copiedFix
                    ? 'Copied!'
                    : `Fix: ${
                        currentSnapshot.job?.explanation?.suggestion ||
                        'pip install pandas'
                      }`}
                </span>
              </button>
            </div>

            <pre className="p-3.5 rounded-lg bg-[#141517] text-slate-200 font-mono text-xs overflow-x-auto whitespace-pre-wrap">
              {currentSnapshot.job?.excerpt ||
                "Authorization: [REDACTED]\nModuleNotFoundError: No module named 'pandas'"}
            </pre>
          </div>
        )}

        {/* Bottom Console Row: Wire Event Stream */}
        <div className="arch-cell p-5 sm:p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-[#787C82] font-semibold">
              CHRONOLOGICAL WIRE STREAM ({currentEvents.length} EVENTS)
            </span>
            <button
              onClick={handleClearEvents}
              className="inline-flex items-center gap-1 text-xs text-[#787C82] hover:text-red-600 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          </div>

          {currentEvents.length === 0 ? (
            <div className="py-6 text-center text-xs text-[#787C82]">
              No events recorded in this session yet.
            </div>
          ) : (
            <div className="divide-y divide-black/[0.06] dark:divide-white/[0.06] text-xs">
              {currentEvents.map((evt) => (
                <div
                  key={evt.id}
                  className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white font-semibold">
                      {evt.badgeText}
                    </span>
                    <span className="font-semibold text-[#141517] dark:text-white">
                      {evt.title}
                    </span>
                    <span className="text-[#4A4D52] dark:text-[#9CA3AF] hidden md:inline">
                      — {evt.detail}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-[#787C82]">
                    {formatRelativeTime(evt.timestamp)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
