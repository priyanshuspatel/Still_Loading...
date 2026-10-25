/**
 * Matrix Engine for Still Loading...
 * Directly mirrors `shared/matrix_display.py` and `uno-q/sketch/sketch.ino`.
 * 
 * Hardware characteristics:
 * - 8 rows x 13 columns = 104 blue LEDs
 * - 3-bit grayscale per pixel (0 = OFF, 1 = dimmest, 7 = maximum brightness)
 * - Companion RGB LED 3 state colors
 */

import { HardwareLightState } from '../types/telemetry';

export const ROWS = 8;
export const COLS = 13;
export const MAX_BRIGHTNESS = 7;

export type MatrixFrame = number[][]; // 8 rows x 13 cols, values 0..7

// Timing constants in milliseconds (mirrored from shared/matrix_display.py)
export const START_HEART_BLINKS = 2;
export const START_HEART_PERIOD_MS = 650;
export const START_HEART_ON_MS = 400;
export const START_INTRO_MS = START_HEART_BLINKS * START_HEART_PERIOD_MS;

export const RUNNING_CYCLE_MS = 8000;
export const RUNNING_PERCENT_MS = 4400;
export const RUNNING_WAIT_MS = 6600;
export const DOT_STEP_MS = 450;
export const SLOW_STEP_MS = 700;

export const COMPLETE_HEART_BLINKS = 3;
export const COMPLETE_HEART_PERIOD_MS = 750;
export const COMPLETE_HEART_ON_MS = 450;
export const COMPLETE_HEART_TOTAL_MS = COMPLETE_HEART_BLINKS * COMPLETE_HEART_PERIOD_MS;
export const COMPLETE_PERCENT_MS = COMPLETE_HEART_TOTAL_MS + 1800;
export const DOWNLOAD_COMPLETE_PERCENT_MS = 1800;

// 3x5 pixel glyphs rendered on rows 1..5
export const DIGIT_GLYPHS: Record<string, string[]> = {
  '0': ['111', '101', '101', '101', '111'],
  '1': ['010', '110', '010', '010', '111'],
  '2': ['111', '001', '111', '100', '111'],
  '3': ['111', '001', '111', '001', '111'],
  '4': ['101', '101', '111', '001', '001'],
  '5': ['111', '100', '111', '001', '111'],
  '6': ['111', '100', '111', '101', '111'],
  '7': ['111', '001', '001', '001', '001'],
  '8': ['111', '101', '111', '101', '111'],
  '9': ['111', '101', '111', '001', '111'],
  '%': ['110', '001', '010', '100', '011'],
};

// 7x6 heart centered at columns 3..9, rows 1..6
export const HEART_ROWS: string[] = [
  '0110110',
  '1111111',
  '1111111',
  '0111110',
  '0011100',
  '0001000',
];

export function emptyFrame(): MatrixFrame {
  return Array.from({ length: ROWS }, () => Array(COLS).fill(0));
}

export function setPixel(frame: MatrixFrame, row: number, col: number, brightness: number): void {
  if (row >= 0 && row < ROWS && col >= 0 && col < COLS) {
    const clamped = Math.max(0, Math.min(MAX_BRIGHTNESS, Math.round(brightness)));
    frame[row][col] = clamped;
  }
}

export function drawGlyph(
  frame: MatrixFrame,
  glyph: string,
  topRow: number,
  leftCol: number,
  brightness: number
): void {
  const bitmap = DIGIT_GLYPHS[glyph];
  if (!bitmap) return;
  for (let rIdx = 0; rIdx < bitmap.length; rIdx++) {
    const line = bitmap[rIdx];
    for (let cIdx = 0; cIdx < line.length; cIdx++) {
      if (line[cIdx] === '1') {
        setPixel(frame, topRow + rIdx, leftCol + cIdx, brightness);
      }
    }
  }
}

export function drawPercentSymbol(
  frame: MatrixFrame,
  topRow: number,
  leftCol: number,
  brightness: number
): void {
  // Upper circle (shifted 1 LED unit left and closed as a complete 2x2 block)
  setPixel(frame, topRow, leftCol - 1, brightness);
  setPixel(frame, topRow, leftCol, brightness);
  setPixel(frame, topRow + 1, leftCol - 1, brightness);
  setPixel(frame, topRow + 1, leftCol, brightness);

  // Straight diagonal slash, from upper right to lower left (extended 1 LED unit downward)
  setPixel(frame, topRow, leftCol + 3, brightness);
  setPixel(frame, topRow + 1, leftCol + 2, brightness);
  setPixel(frame, topRow + 2, leftCol + 1, brightness);
  setPixel(frame, topRow + 3, leftCol, brightness);
  setPixel(frame, topRow + 4, leftCol - 1, brightness);

  // Lower circle (complete 2x2 block)
  setPixel(frame, topRow + 3, leftCol + 2, brightness);
  setPixel(frame, topRow + 3, leftCol + 3, brightness);
  setPixel(frame, topRow + 4, leftCol + 2, brightness);
  setPixel(frame, topRow + 4, leftCol + 3, brightness);
}

export function drawProgressBar(
  frame: MatrixFrame,
  row: number,
  progress: number,
  brightness: number = 3
): void {
  const clamped = Math.max(0, Math.min(100, Math.round(progress)));
  if (clamped <= 0) return;
  const lit = Math.max(1, Math.floor((clamped * COLS) / 100));
  for (let c = 0; c < lit; c++) {
    setPixel(frame, row, c, brightness);
  }
}

export function renderHeartFrame(brightness: number = 5, progress?: number | null): MatrixFrame {
  const frame = emptyFrame();
  for (let rIdx = 0; rIdx < HEART_ROWS.length; rIdx++) {
    const line = HEART_ROWS[rIdx];
    for (let cIdx = 0; cIdx < line.length; cIdx++) {
      if (line[cIdx] === '1') {
        setPixel(frame, 1 + rIdx, 3 + cIdx, brightness);
      }
    }
  }
  if (progress !== undefined && progress !== null && progress > 0) {
    drawProgressBar(frame, 7, progress, 3);
  }
  return frame;
}

export function renderWaitingDotsFrame(
  activeDot: number = 0,
  progress?: number | null,
  slow: boolean = false
): MatrixFrame {
  const frame = emptyFrame();
  const cols = [3, 6, 9];
  const active = ((activeDot % 3) + 3) % 3;
  for (let idx = 0; idx < cols.length; idx++) {
    const col = cols[idx];
    const level = idx === active ? 5 : 2;
    setPixel(frame, 3, col, level);
    if (slow) {
      setPixel(frame, 4, col, idx === active ? 3 : 1);
    }
  }
  if (slow) {
    setPixel(frame, 6, 1, 3);
    setPixel(frame, 6, 11, 3);
  }
  if (progress !== undefined && progress !== null && progress > 0) {
    drawProgressBar(frame, 7, progress, 4);
  }
  return frame;
}

export function renderPercentageFrame(
  percent: number,
  options: {
    charging?: boolean;
    slow?: boolean;
    pulseStep?: number;
  } = {}
): MatrixFrame {
  const frame = emptyFrame();
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));

  if (clamped === 100) {
    drawGlyph(frame, '1', 1, 1, 6);
    drawGlyph(frame, '0', 1, 5, 6);
    drawGlyph(frame, '0', 1, 9, 6);
    for (let c = 0; c < COLS; c++) {
      setPixel(frame, 7, c, 5);
    }
  } else if (clamped < 10) {
    drawGlyph(frame, String(clamped), 1, 2, 6);
    drawPercentSymbol(frame, 1, 8, 4);
  } else {
    drawGlyph(frame, String(Math.floor(clamped / 10)), 1, 0, 6);
    drawGlyph(frame, String(clamped % 10), 1, 4, 6);
    drawPercentSymbol(frame, 1, 9, 4);
  }

  if (clamped !== 100) {
    if (options.charging) {
      drawProgressBar(frame, 7, clamped, 3);
      const head = (options.pulseStep ?? 0) % COLS;
      setPixel(frame, 7, head, 6);
    } else if (options.slow) {
      drawProgressBar(frame, 7, clamped, 3);
      setPixel(frame, 6, 0, 3);
      setPixel(frame, 6, COLS - 1, 3);
    } else if (clamped > 0) {
      drawProgressBar(frame, 7, clamped, 3);
    }
  }

  return frame;
}

export function renderStallFrame(blinkOn: boolean = true, progress?: number | null): MatrixFrame {
  const frame = emptyFrame();
  const level = blinkOn ? 6 : 3;
  for (const r of [1, 2, 3, 4]) {
    setPixel(frame, r, 6, level);
  }
  setPixel(frame, 6, 6, level);

  // Side warning brackets
  for (const r of [2, 3, 4, 5]) {
    setPixel(frame, r, 2, blinkOn ? 3 : 1);
    setPixel(frame, r, 10, blinkOn ? 3 : 1);
  }

  if (progress !== undefined && progress !== null && progress > 0) {
    drawProgressBar(frame, 7, progress, 2);
  }
  return frame;
}

export function renderFailedFrame(): MatrixFrame {
  const frame = emptyFrame();
  for (let i = 0; i < 5; i++) {
    setPixel(frame, 1 + i, 4 + i, 7);
    setPixel(frame, 1 + i, 8 - i, 7);
  }
  setPixel(frame, 1, 1, 4);
  setPixel(frame, 5, 1, 4);
  setPixel(frame, 1, 11, 4);
  setPixel(frame, 5, 11, 4);
  return frame;
}

export function renderCompletedCheckFrame(): MatrixFrame {
  const frame = emptyFrame();
  const points: [number, number][] = [
    [4, 3],
    [5, 4],
    [4, 5],
    [3, 6],
    [2, 7],
    [1, 8],
  ];
  for (const [r, c] of points) {
    setPixel(frame, r, c, 5);
  }
  for (let c = 3; c < 10; c++) {
    setPixel(frame, 7, c, 2);
  }
  return frame;
}

export function renderUnavailableFrame(): MatrixFrame {
  const frame = emptyFrame();
  for (const c of [3, 4, 5, 7, 8, 9]) {
    setPixel(frame, 3, c, 3);
  }
  return frame;
}

export interface FrameResult {
  kind: string;
  frame: MatrixFrame;
  description: string;
  led3: {
    color: string;
    pulse: boolean;
    name: string;
  };
}

/**
 * Maps state and elapsed time to the exact 8x13 matrix frame and RGB LED 3 status.
 */
export function selectDisplayFrame(
  state: HardwareLightState,
  progress: number = 0,
  elapsedMs: number = 0,
  progressKnown: boolean = true
): FrameResult {
  const ms = Math.max(0, elapsedMs);

  switch (state) {
    case 'idle': {
      const dot = Math.floor(ms / DOT_STEP_MS) % 3;
      return {
        kind: 'idle_dots',
        frame: renderWaitingDotsFrame(dot, null),
        description: 'Waiting dots stepping gently',
        led3: { color: '#64748b', pulse: false, name: 'Dim Neutral' },
      };
    }

    case 'running': {
      const led3 = { color: '#38bdf8', pulse: true, name: 'Calm Blue Pulse' };
      if (ms < START_INTRO_MS) {
        const within = ms % START_HEART_PERIOD_MS;
        const bright = within < START_HEART_ON_MS ? 5 : 1;
        return {
          kind: 'start_heart',
          frame: renderHeartFrame(bright, progressKnown ? progress : null),
          description: 'Job start: centered heart pulse',
          led3,
        };
      }
      const cycle = (ms - START_INTRO_MS) % RUNNING_CYCLE_MS;
      if (progressKnown && progress >= 0 && progress <= 100) {
        if (cycle < RUNNING_PERCENT_MS) {
          return {
            kind: 'percentage',
            frame: renderPercentageFrame(progress),
            description: `Active progress ${progress}%`,
            led3,
          };
        }
        if (cycle < RUNNING_WAIT_MS) {
          const dot = Math.floor(ms / DOT_STEP_MS) % 3;
          return {
            kind: 'waiting_dots',
            frame: renderWaitingDotsFrame(dot, progress),
            description: `Progress ${progress}% with waiting dots`,
            led3,
          };
        }
        return {
          kind: 'heartbeat',
          frame: renderHeartFrame(4, progress),
          description: `Progress ${progress}% heartbeat cue`,
          led3,
        };
      }
      // Unknown percentage
      if (cycle < RUNNING_WAIT_MS) {
        const dot = Math.floor(ms / DOT_STEP_MS) % 3;
        return {
          kind: 'waiting_dots',
          frame: renderWaitingDotsFrame(dot, null),
          description: 'Job active (percentage indeterminate)',
          led3,
        };
      }
      return {
        kind: 'heartbeat',
        frame: renderHeartFrame(4, null),
        description: 'Job active heartbeat',
        led3,
      };
    }

    case 'slow': {
      const led3 = { color: '#fbbf24', pulse: false, name: 'Warm Amber' };
      const cycle = ms % RUNNING_CYCLE_MS;
      if (progressKnown && progress >= 0 && progress <= 100 && cycle < RUNNING_PERCENT_MS) {
        return {
          kind: 'slow_percentage',
          frame: renderPercentageFrame(progress, { slow: true }),
          description: `Slow progress ${progress}% with corner cues`,
          led3,
        };
      }
      const dot = Math.floor(ms / SLOW_STEP_MS) % 3;
      return {
        kind: 'slow_waiting',
        frame: renderWaitingDotsFrame(dot, progressKnown ? progress : null, true),
        description: 'Slow waiting dots (2-row step)',
        led3,
      };
    }

    case 'suspected_stall': {
      const blinkOn = Math.floor(ms / 400) % 2 === 0;
      return {
        kind: 'suspected_stall',
        frame: renderStallFrame(blinkOn, progressKnown ? progress : null),
        description: 'Suspected stall: missing heartbeat warning [ ! ]',
        led3: { color: '#f59e0b', pulse: true, name: 'Magenta/Amber Pulse' },
      };
    }

    case 'failed': {
      return {
        kind: 'failed_x',
        frame: renderFailedFrame(),
        description: 'Failed job: steady X with corner markers',
        led3: { color: '#ef4444', pulse: false, name: 'Steady Red' },
      };
    }

    case 'completed': {
      const led3 = { color: '#22c55e', pulse: false, name: 'Calm Green' };
      if (ms < COMPLETE_HEART_TOTAL_MS) {
        const within = ms % COMPLETE_HEART_PERIOD_MS;
        const bright = within < COMPLETE_HEART_ON_MS ? 5 : 1;
        return {
          kind: 'completed_heart',
          frame: renderHeartFrame(bright, 100),
          description: 'Job completed: celebratory heart pulse',
          led3,
        };
      }
      if (ms < COMPLETE_PERCENT_MS) {
        return {
          kind: 'completed_100',
          frame: renderPercentageFrame(100),
          description: 'Job completed: 100% full bar',
          led3,
        };
      }
      return {
        kind: 'completed_check',
        frame: renderCompletedCheckFrame(),
        description: 'Job completed: steady checkmark',
        led3,
      };
    }

    case 'battery': {
      const isFull = progress >= 100;
      return {
        kind: 'battery_percent',
        frame: renderPercentageFrame(progress),
        description: `MacBook battery at ${progress}%`,
        led3: {
          color: isFull ? '#22c55e' : '#14b8a6',
          pulse: false,
          name: isFull ? 'Full Green' : 'Calm Teal',
        },
      };
    }

    case 'battery_charging': {
      const step = Math.floor(ms / 250);
      return {
        kind: 'battery_charging',
        frame: renderPercentageFrame(progress, { charging: true, pulseStep: step }),
        description: `MacBook charging at ${progress}% (animated bar)`,
        led3: { color: '#10b981', pulse: true, name: 'Warm Green-Cyan Pulse' },
      };
    }

    case 'battery_unavailable': {
      return {
        kind: 'battery_unavailable',
        frame: renderUnavailableFrame(),
        description: 'Battery state unavailable (--)',
        led3: { color: '#64748b', pulse: false, name: 'Dim Neutral' },
      };
    }

    case 'download': {
      const isComplete = progress >= 100;
      const led3 = {
        color: isComplete ? '#22c55e' : '#0284c7',
        pulse: !isComplete,
        name: isComplete ? 'Download Complete Green' : 'Cyan-Blue Progress',
      };
      if (!progressKnown) {
        const dot = Math.floor(ms / DOT_STEP_MS) % 3;
        return {
          kind: 'download_waiting',
          frame: renderWaitingDotsFrame(dot, null),
          description: 'Chrome download initializing',
          led3,
        };
      }
      if (isComplete) {
        if (ms < DOWNLOAD_COMPLETE_PERCENT_MS) {
          return {
            kind: 'download_100',
            frame: renderPercentageFrame(100),
            description: 'Chrome download 100% full bar',
            led3,
          };
        }
        return {
          kind: 'download_check',
          frame: renderCompletedCheckFrame(),
          description: 'Chrome download complete checkmark',
          led3,
        };
      }
      return {
        kind: 'download_percent',
        frame: renderPercentageFrame(progress),
        description: `Chrome download progress ${progress}%`,
        led3,
      };
    }

    default:
      return {
        kind: 'idle_dots',
        frame: renderWaitingDotsFrame(0, null),
        description: 'Matrix idle',
        led3: { color: '#64748b', pulse: false, name: 'Dim Neutral' },
      };
  }
}
