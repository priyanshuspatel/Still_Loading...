/**
 * Pure Control Deck feed and command rules.
 * The browser asks the backend for an allowlisted action. It never sends a shell command.
 */

export type ControlAction =
  | 'battery'
  | 'download'
  | 'job_success'
  | 'job_failure'
  | 'completed'
  | 'idle'
  | 'reset'
  | 'stop'
  | 'demo'
  | 'gemma'
  | 'connection';

export type ButtonPhase = 'idle' | 'running' | 'success' | 'error' | 'disabled';

export interface ControlButton {
  action: ControlAction;
  label: string;
}

export const CONTROL_BUTTONS: ControlButton[] = [
  { action: 'battery', label: 'Battery' },
  { action: 'download', label: 'Chrome Download' },
  { action: 'job_success', label: 'Run Job' },
  { action: 'completed', label: 'Completed' },
  { action: 'job_failure', label: 'Failed' },
  { action: 'idle', label: 'Idle' },
  { action: 'reset', label: 'Reset' },
  { action: 'stop', label: 'Stop' },
  { action: 'gemma', label: 'Gemma Analysis' },
  { action: 'demo', label: 'Demo' },
  { action: 'connection', label: 'Connection Test' },
];

const ALWAYS_ENABLED = new Set<ControlAction>(['stop', 'connection', 'gemma']);

export interface FeedEvent {
  id: number | string;
  timestamp: string;
  source: string;
  action: string;
  level?: string;
  simulated?: boolean;
  pending?: boolean;
}

export interface MatrixPayload {
  frame_kind?: string;
  frame?: number[][];
  state?: string;
  progress?: number;
  simulated?: boolean;
}

export interface ControlSnapshot {
  uno_q: 'connected' | 'offline' | string;
  lights: {
    state: string;
    code?: number;
    progress?: number;
    progress_known?: boolean;
    display_mode?: string;
    charging_state?: string | null;
    job_id?: string | null;
  };
  battery: {
    available?: boolean;
    percent?: number | null;
    charging_state?: string;
    simulated?: boolean;
  };
  download: {
    active?: boolean;
    state?: string;
    progress?: number;
    progress_known?: boolean;
    downloaded_bytes?: number;
    total_bytes?: number | null;
    simulated?: boolean;
  };
  job?: {
    job_id?: string;
    event?: string;
    progress?: number;
    is_failure?: boolean;
    excerpt?: string | null;
    explanation?: Record<string, unknown> | null;
  } | null;
  gemma?: Record<string, unknown> | null;
  matrix?: MatrixPayload;
  events?: FeedEvent[];
  demo?: { active?: boolean; simulated?: boolean; label?: string | null };
  active_action?: string | null;
  timestamp?: number;
}

export function controlPath(action: ControlAction): { path: string; body: Record<string, string> } {
  switch (action) {
    case 'battery':
      return { path: '/v1/control/battery', body: {} };
    case 'download':
      return { path: '/v1/control/download', body: {} };
    case 'idle':
      return { path: '/v1/control/idle', body: {} };
    case 'reset':
      return { path: '/v1/control/reset', body: {} };
    case 'stop':
      return { path: '/v1/control/stop', body: {} };
    case 'demo':
      return { path: '/v1/control/demo', body: { action: 'demo' } };
    case 'gemma':
      return { path: '/v1/control/gemma', body: {} };
    case 'connection':
      return { path: '/v1/control/connection', body: {} };
    default:
      return { path: '/v1/control/job', body: { action } };
  }
}

export function controlLocked(active: string | null | undefined, pending: string | null): boolean {
  return Boolean(active || pending);
}

export function buttonDisabled(action: ControlAction, locked: boolean): boolean {
  if (ALWAYS_ENABLED.has(action)) return false;
  return locked;
}

export function buttonPhase(
  action: ControlAction,
  options: {
    pending: ControlAction | null;
    active?: string | null;
    held?: ControlAction | null;
    last?: Partial<Record<ControlAction, 'success' | 'error'>>;
  }
): ButtonPhase {
  const busy = options.pending === action || options.active === action || options.held === action;
  if (busy) return 'running';
  if (buttonDisabled(action, controlLocked(options.active, options.pending || options.held || null))) {
    return 'disabled';
  }
  return options.last?.[action] ?? 'idle';
}

export function modeLabel(mode: string | undefined): string {
  if (mode === 'job') return 'JOB MODE';
  if (mode === 'battery') return 'BATTERY MODE';
  return 'AUTO MODE';
}

export function matrixReadout(snapshot: ControlSnapshot): string {
  const simulated = Boolean(snapshot.demo?.simulated || snapshot.matrix?.simulated);
  const prefix = simulated ? 'DEMO / SIMULATED · ' : '';
  const state = snapshot.lights.state;
  const progress = snapshot.lights.progress ?? 0;
  const charge = snapshot.lights.charging_state || snapshot.battery.charging_state || 'unknown';
  if (state === 'battery' || state === 'battery_charging') return `${prefix}Battery ${progress}% ${charge}`;
  if (state === 'battery_unavailable') return `${prefix}Battery unavailable`;
  if (state === 'download') return `${prefix}Download ${progress}%`;
  if (state === 'failed') return `${prefix}Failed`;
  if (state === 'suspected_stall') return `${prefix}Stall`;
  if (state === 'slow') return `${prefix}Slow ${progress}%`;
  if (state === 'completed') return `${prefix}Completed`;
  if (state === 'running') return `${prefix}Job ${progress}%`;
  return `${prefix}${state}`;
}

export function formatClock(now: Date): string {
  return now.toLocaleTimeString('en-GB', { hour12: false });
}

export function optimisticCommand(action: ControlAction, now = new Date()): FeedEvent {
  const button = CONTROL_BUTTONS.find((item) => item.action === action);
  return {
    id: `local-${now.getTime()}`,
    timestamp: formatClock(now),
    source: 'COMMAND',
    action: `${button?.label ?? action} requested`,
    pending: true,
  };
}

export function mergeFeed(current: FeedEvent[], incoming: FeedEvent[] | undefined): FeedEvent[] {
  const pending = current.filter((event) => event.pending);
  const server = (incoming ?? []).filter((event) => !event.pending);
  const seen = new Set(server.map((event) => String(event.id)));
  const extras = pending.filter((event) => !seen.has(String(event.id)));
  return [...server, ...extras].slice(-80);
}

export function unoStatusLabel(uno: string | undefined): string {
  return uno === 'connected' ? 'UNO Q ● CONNECTED' : 'UNO Q ● OFFLINE';
}

export function gemmaUnavailableCopy(gemma: Record<string, unknown> | null | undefined): string | null {
  if (!gemma) return null;
  if (gemma.verification_status === 'unavailable') {
    return 'Gemma unavailable — rules explanation used';
  }
  return null;
}

export function feedLine(event: FeedEvent): string {
  const sim = event.simulated ? '  DEMO / SIMULATED' : '';
  return `${event.timestamp}  ${event.source}  ${event.action}${sim}`;
}
