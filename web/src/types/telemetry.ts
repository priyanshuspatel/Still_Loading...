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

export interface GemmaEvidenceItem {
  log_line: string;
  reason: string;
  found?: boolean;
}

export type GemmaVerificationStatus =
  | 'verified'
  | 'unverified'
  | 'unavailable'
  | 'timeout'
  | 'malformed';

export interface FailureExplanation {
  category: string;
  summary: string;
  suggestion: string;
  confidence?: number;
  source?: string;
  severity?: 'info' | 'warning' | 'error' | 'critical' | string;
  verification_status?: GemmaVerificationStatus | string;
  diagnosis?: string;
  recommended_action?: string;
  evidence?: GemmaEvidenceItem[];
  fallback_summary?: string;
  detail?: string;
}

export interface JobReading {
  job_id: string;
  event?: string;
  progress: number;
  exit_code?: number | null;
  is_failure: boolean;
  message?: string;
  excerpt?: string | null;
  explanation?: FailureExplanation | null;
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
  job?: JobReading | null;
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

export interface JobHistoryRecord {
  job_id: string;
  event: string;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  progress: number;
  exit_code: number | null;
  is_failure: boolean;
  message?: string | null;
  category?: string | null;
  summary?: string | null;
  suggestion?: string | null;
  excerpt?: string | null;
  explanation?: FailureExplanation | null;
  accepted_count: number;
  highest_sequence: number;
  created_at: string;
}

export interface HistoryStats {
  total_jobs: number;
  completed_count: number;
  failed_count: number;
  success_rate: number;
  avg_duration_seconds: number;
  total_duration_seconds: number;
  failure_categories: Record<string, number>;
}

