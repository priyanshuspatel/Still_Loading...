import React, { useEffect, useState } from 'react';
import { LEDMatrix } from './LEDMatrix';
import { GemmaAnalysisCard } from './GemmaAnalysisCard';
import { gemmaCardModel } from '../lib/gemmaCard';
import { fetchControlState, postControl } from '../lib/controlClient';
import {
  CONTROL_BUTTONS,
  ControlAction,
  ControlSnapshot,
  FeedEvent,
  buttonPhase,
  controlLocked,
  feedLine,
  gemmaUnavailableCopy,
  matrixReadout,
  mergeFeed,
  modeLabel,
  optimisticCommand,
  unoStatusLabel,
} from '../lib/controlDeckModel';
import { FailureExplanation, HardwareLightState } from '../types/telemetry';

const EMPTY: ControlSnapshot = {
  uno_q: 'offline',
  lights: { state: 'idle', progress: 0, progress_known: false, code: 0, display_mode: 'auto' },
  battery: { available: false, percent: null, charging_state: 'unknown' },
  download: { active: false, state: 'idle', progress: 0, progress_known: false, downloaded_bytes: 0, total_bytes: null },
  job: null,
  gemma: null,
  events: [],
  demo: { active: false, simulated: false, label: null },
};

interface ControlDeckProps {
  autoPoll?: boolean;
  initialState?: ControlSnapshot | null;
  presentationDefault?: boolean;
  onOpenDeveloper?: () => void;
}

export const ControlDeck: React.FC<ControlDeckProps> = ({
  autoPoll = true,
  initialState = null,
  presentationDefault = false,
  onOpenDeveloper,
}) => {
  const [snapshot, setSnapshot] = useState<ControlSnapshot>(initialState ?? EMPTY);
  const [feed, setFeed] = useState<FeedEvent[]>(initialState?.events ?? []);
  const [presentation, setPresentation] = useState(presentationDefault);
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<ControlAction | null>(null);
  const [heldAction, setHeldAction] = useState<ControlAction | null>(null);
  const [lastPhase, setLastPhase] = useState<Partial<Record<ControlAction, 'success' | 'error'>>>({});

  useEffect(() => {
    if (!autoPoll) return;
    let alive = true;
    const pull = async () => {
      try {
        const next = await fetchControlState();
        if (!alive) return;
        setSnapshot(next);
        setFeed((current) => mergeFeed(current, next.events));
        setError(null);
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : 'Control Deck unreachable');
      }
    };
    void pull();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void pull();
    }, 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [autoPoll]);

  useEffect(() => {
    if (heldAction && !snapshot.active_action && !pendingAction) setHeldAction(null);
  }, [heldAction, snapshot.active_action, pendingAction]);

  const onCommand = async (action: ControlAction) => {
    const locked = controlLocked(snapshot.active_action || heldAction, pendingAction);
    if (buttonPhase(action, { pending: pendingAction, active: snapshot.active_action, held: heldAction, last: lastPhase }) === 'disabled') {
      return;
    }
    if (locked && action !== 'stop' && action !== 'connection' && action !== 'gemma') {
      return;
    }
    const optimistic = optimisticCommand(action);
    setFeed((current) => [...current, optimistic].slice(-80));
    setPendingAction(action);
    try {
      const result = await postControl(action);
      const events = (result.body.events as FeedEvent[] | undefined) ?? [];
      const state = result.body.state as ControlSnapshot | undefined;
      if (state) setSnapshot(state);
      setFeed((current) => mergeFeed(current.filter((event) => event.id !== optimistic.id), events.length ? events : state?.events));
      if (result.status >= 400) {
        const detail = String(result.body.detail || result.body.reason || 'request rejected');
        setLastPhase((current) => ({ ...current, [action]: 'error' }));
        setFeed((current) => [
          ...current,
          {
            id: `error-${Date.now()}`,
            timestamp: optimistic.timestamp,
            source: 'ERROR',
            action: detail,
            level: 'error',
            pending: true,
          },
        ]);
      } else {
        setLastPhase((current) => ({ ...current, [action]: 'success' }));
        if (result.status === 202) setHeldAction(action);
      }
      setError(null);
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'request failed';
      setLastPhase((current) => ({ ...current, [action]: 'error' }));
      setError(detail);
      setFeed((current) => [
        ...current,
        {
          id: `error-${Date.now()}`,
          timestamp: optimistic.timestamp,
          source: 'ERROR',
          action: detail,
          level: 'error',
          pending: true,
        },
      ]);
    } finally {
      setPendingAction(null);
    }
  };

  const lights = snapshot.lights;
  const matrixState = (lights.state || 'idle') as HardwareLightState;
  const simulated = Boolean(snapshot.demo?.simulated || snapshot.matrix?.simulated);
  const gemmaRecord = (snapshot.gemma ?? snapshot.job?.explanation) as FailureExplanation | null | undefined;
  const gemma = gemmaCardModel(gemmaRecord, matrixState === 'failed' || snapshot.job?.is_failure ? 'failed' : matrixState);
  const unavailable = gemmaUnavailableCopy(gemmaRecord as Record<string, unknown> | null);
  const connected = snapshot.uno_q === 'connected';
  const readout = matrixReadout(snapshot);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4">
      <header className="arch-cell px-4 py-3 sm:px-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-[#787C82]">Still Loading</p>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Control Deck</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full px-3 py-1 text-xs font-mono bg-[#141517] text-white" data-mode={lights.display_mode ?? 'auto'}>
            {modeLabel(lights.display_mode)}
          </span>
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-mono ${
              connected ? 'bg-emerald-600 text-white' : 'bg-[#4A4D52] text-white'
            }`}
            data-uno={snapshot.uno_q}
          >
            {unoStatusLabel(snapshot.uno_q)}
          </span>
          <button type="button" className="deck-button" onClick={() => setPresentation((value) => !value)}>
            {presentation ? 'Show developer details' : 'Presentation mode'}
          </button>
          {onOpenDeveloper && (
            <button type="button" className="deck-button" onClick={onOpenDeveloper}>
              Developer dashboard
            </button>
          )}
        </div>
      </header>

      {error && (
        <p className="text-sm text-red-700 dark:text-red-300" role="status">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[240px_minmax(0,1fr)_300px] gap-4 items-start">
        <section className="arch-cell p-4 space-y-2" aria-label="Control">
          <h2 className="text-sm font-semibold tracking-wide">CONTROL</h2>
          {CONTROL_BUTTONS.map((button) => {
            const phase = buttonPhase(button.action, {
              pending: pendingAction,
              active: snapshot.active_action,
              held: heldAction,
              last: lastPhase,
            });
            return (
              <button
                key={button.action}
                type="button"
                data-action={button.action}
                data-phase={phase}
                className="deck-button w-full text-left"
                disabled={phase === 'disabled' || (phase === 'running' && button.action !== 'stop')}
                onClick={() => void onCommand(button.action)}
              >
                {button.label}
                {phase === 'running' ? ' …' : ''}
              </button>
            );
          })}
          {!presentation && (
            <p className="text-xs text-[#4A4D52] dark:text-[#9CA3AF] pt-1">
              Auto mode shows a download first, then an active job, then battery.
            </p>
          )}
        </section>

        <div className="space-y-4">
          <section className="arch-cell p-4 sm:p-5 space-y-3" aria-label="Live LED matrix">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold tracking-wide">LED MATRIX 8×13</h2>
              {simulated && (
                <span className="font-mono text-[11px] uppercase bg-amber-500 text-[#141517] px-2 py-0.5 rounded">
                  DEMO / SIMULATED
                </span>
              )}
            </div>
            <p className="font-mono text-sm font-semibold" data-readout>
              {readout}
            </p>
            <LEDMatrix
              state={matrixState}
              progress={Number(lights.progress ?? 0)}
              progressKnown={lights.progress_known !== false}
              interactive={false}
              size="md"
              showLabels={!presentation}
            />
            {!presentation && (
              <p className="font-mono text-xs text-[#4A4D52] dark:text-[#9CA3AF]">
                state={lights.state} code={lights.code ?? 0} progress={lights.progress ?? 0} mode=
                {lights.display_mode ?? 'auto'}
              </p>
            )}
          </section>
          <section aria-label="Gemma analysis">
            {unavailable && (
              <p className="mb-3 text-sm font-medium text-amber-800 dark:text-amber-200">{unavailable}</p>
            )}
            {gemma ? (
              <div className="space-y-3">
                <GemmaAnalysisCard model={gemma} />
                {snapshot.job?.excerpt && (
                  <pre className="arch-cell p-4 font-mono text-xs whitespace-pre-wrap text-[#141517] dark:text-[#E5E7EB]">
                    {snapshot.job.excerpt}
                  </pre>
                )}
              </div>
            ) : (
              <div className="arch-cell p-5">
                <h2 className="text-sm font-semibold tracking-wide mb-2">GEMMA ANALYSIS</h2>
                <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF]">
                  No failure analysis yet. Failed runs Gemma on the Mac when it is enabled.
                </p>
              </div>
            )}
          </section>
        </div>

        <section className="arch-cell p-4 sm:p-5 space-y-3 xl:sticky xl:top-24" aria-label="Live event feed">
          <h2 className="text-sm font-semibold tracking-wide">LIVE FEED</h2>
          <ol className="max-h-[70vh] overflow-auto rounded-lg bg-[#141517] text-[#E5E7EB] font-mono text-xs p-3 space-y-1" data-feed>
            {feed.length === 0 && <li className="text-[#9CA3AF]">Waiting for the control service.</li>}
            {feed.map((event) => (
              <li key={String(event.id)} className={event.level === 'error' ? 'text-red-300' : undefined}>
                {feedLine(event)}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
};
