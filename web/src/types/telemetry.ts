/**
 * Still Loading... Telemetry Type Definitions
 * Strict types representing the exact hardware & agent contracts.
 */

export type DisplayMode = 'auto' | 'job' | 'battery';

export type HardwareLightState =
  | 'idle'
  | 'running'
  | 'slow'
  | 'suspected_stall'
  | 'failed'
  | 'completed'
  | 'battery'
  | 'battery_charging'
  | 'battery_unavailable'
  | 'download';

export type ChargingState = 'charging' | 'discharging' | 'full' | 'unknown';

export type DownloadStatus = 'idle' | 'starting' | 'downloading' | 'completed' | 'failed' | 'cancelled';

export interface BatteryReading {
  available: boolean;
  percent: number | null;
  charging_state: ChargingState;
  timestamp?: number;
  time_remaining_minutes?: number | null;
  source?: 'pmset' | 'simulated';
}

export interface DownloadReading {
  active: boolean;
  download_id: string | null;
  state: DownloadStatus;
  progress: number;
  progress_known: boolean;
  downloaded_bytes: number;
  total_bytes: number | null;
  speed_bytes_sec?: number;
  filename_display?: string; // Sanitized display name only, no local filesystem paths
  timestamp?: number;
}

export interface LightsReading {
  state: HardwareLightState;
  code: number;
  job_id: string | null;
  progress: number;
  sequence: number;
  progress_known: boolean;
  display_mode: DisplayMode;
  charging_state: string | null;
}

export interface ConnectionHealth {
  dataService: 'online' | 'degraded' | 'offline';
  macAgent: 'active' | 'stale' | 'offline' | 'not_verified';
  receiver: 'reachable' | 'unreachable' | 'not_verified';
  matrixHardware: 'verified' | 'unverified';
  lastPingMs?: number;
  latencyMs?: number;
}

export interface TelemetrySnapshot {
  timestamp: number;
  is_live: boolean;
  source_label: 'Live Telemetry' | 'Interactive Demo';
  battery: BatteryReading;
  download: DownloadReading;
  lights: LightsReading;
  connection: ConnectionHealth;
  is_stale: boolean;
  last_updated_text: string;
}

export interface ActivityEvent {
  id: string;
  timestamp: number;
  type: 'battery' | 'download' | 'job' | 'stall' | 'connection' | 'mode';
  title: string;
  detail: string;
  badgeText: string;
  severity: 'info' | 'success' | 'warning' | 'error' | 'neutral';
  is_demo?: boolean;
}
