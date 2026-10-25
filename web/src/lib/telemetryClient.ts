import {
  TelemetrySnapshot,
  BatteryReading,
  DownloadReading,
  LightsReading,
  ConnectionHealth,
} from '../types/telemetry';

export interface TelemetryConfig {
  endpointUrl: string;
  pollIntervalMs: number;
  timeoutMs: number;
  bearerToken?: string; // Optional if proxy is used; strictly omitted from default public calls
}

export const DEFAULT_TELEMETRY_CONFIG: TelemetryConfig = {
  endpointUrl: import.meta.env.VITE_TELEMETRY_API_URL || '/api/telemetry',
  pollIntervalMs: 3000,
  timeoutMs: 4000,
};

export function formatBytes(bytes: number, decimals = 1): string {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function formatTransferSpeed(bytesPerSec?: number): string {
  if (!bytesPerSec || bytesPerSec <= 0) return '-- MB/s';
  return `${formatBytes(bytesPerSec)}/s`;
}

export function formatRelativeTime(timestampMs: number): string {
  if (!timestampMs) return 'Unknown';
  const diffSec = Math.floor((Date.now() - timestampMs) / 1000);
  if (diffSec < 2) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  return `${diffHours}h ago`;
}

/**
 * Validates and normalizes raw telemetry payload returned from a live telemetry endpoint.
 */
export function normalizeLiveTelemetry(raw: any): TelemetrySnapshot {
  const now = Date.now();
  const rawTs = typeof raw.timestamp === 'number' ? raw.timestamp : now;
  const isStale = now - rawTs > 30000; // >30s without update is considered stale

  const battery: BatteryReading = {
    available: Boolean(raw.battery?.available),
    percent: typeof raw.battery?.percent === 'number' ? Math.max(0, Math.min(100, raw.battery.percent)) : null,
    charging_state: ['charging', 'discharging', 'full', 'unknown'].includes(raw.battery?.charging_state)
      ? raw.battery.charging_state
      : 'unknown',
    timestamp: raw.battery?.timestamp,
    source: 'pmset',
  };

  const download: DownloadReading = {
    active: Boolean(raw.download?.active),
    download_id: raw.download?.download_id || null,
    state: ['idle', 'starting', 'downloading', 'completed', 'failed', 'cancelled'].includes(raw.download?.state)
      ? raw.download.state
      : 'idle',
    progress: typeof raw.download?.progress === 'number' ? Math.max(0, Math.min(100, raw.download.progress)) : 0,
    progress_known: Boolean(raw.download?.progress_known),
    downloaded_bytes: typeof raw.download?.downloaded_bytes === 'number' ? raw.download.downloaded_bytes : 0,
    total_bytes: typeof raw.download?.total_bytes === 'number' ? raw.download.total_bytes : null,
    speed_bytes_sec: raw.download?.speed_bytes_sec,
    filename_display: raw.download?.filename_display || (raw.download?.active ? 'Active Chrome Download' : undefined),
    timestamp: raw.download?.timestamp,
  };

  const lights: LightsReading = {
    state: raw.lights?.state || 'idle',
    code: typeof raw.lights?.code === 'number' ? raw.lights.code : 0,
    job_id: raw.lights?.job_id || null,
    progress: typeof raw.lights?.progress === 'number' ? Math.max(0, Math.min(100, raw.lights.progress)) : 0,
    sequence: typeof raw.lights?.sequence === 'number' ? raw.lights.sequence : 0,
    progress_known: Boolean(raw.lights?.progress_known),
    display_mode: ['auto', 'job', 'battery'].includes(raw.lights?.display_mode) ? raw.lights.display_mode : 'auto',
    charging_state: raw.lights?.charging_state || null,
  };

  const connection: ConnectionHealth = {
    dataService: isStale ? 'degraded' : 'online',
    macAgent: raw.connection?.macAgent || (isStale ? 'stale' : 'active'),
    receiver: raw.connection?.receiver || 'reachable',
    matrixHardware: raw.connection?.matrixHardware || 'verified',
    latencyMs: raw.connection?.latencyMs,
  };

  return {
    timestamp: rawTs,
    is_live: true,
    source_label: 'Live Telemetry',
    battery,
    download,
    lights,
    connection,
    is_stale: isStale,
    last_updated_text: formatRelativeTime(rawTs),
  };
}

/**
 * Fetch a single snapshot from live telemetry endpoint with abort controller and timeout.
 */
export async function fetchLiveSnapshot(
  endpointUrl: string,
  timeoutMs = 4000
): Promise<TelemetrySnapshot> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const startMs = performance.now();
  try {
    const res = await fetch(endpointUrl, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latencyMs = Math.round(performance.now() - startMs);

    if (!res.ok) {
      throw new Error(`Telemetry service responded with HTTP ${res.status} (${res.statusText})`);
    }

    const json = await res.json();
    const snapshot = normalizeLiveTelemetry(json);
    snapshot.connection.latencyMs = latencyMs;
    return snapshot;
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error(`Connection timed out after ${timeoutMs}ms`);
    }
    throw err;
  }
}
