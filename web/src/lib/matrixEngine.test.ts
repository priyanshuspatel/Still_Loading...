/**
 * Automated test suite for matrixEngine.ts.
 * Verifies that:
 * 1. Every generated frame has exactly 8 rows and 13 columns (104 pixels).
 * 2. Every pixel value is an integer between 0 and 7 (3-bit grayscale).
 * 3. All states (idle, running, slow, stall, failed, completed, battery, download)
 *    produce valid frames without throwing.
 */

import {
  COLS,
  ROWS,
  MAX_BRIGHTNESS,
  emptyFrame,
  selectDisplayFrame,
  renderPercentageFrame,
  renderHeartFrame,
  renderWaitingDotsFrame,
  renderStallFrame,
  renderFailedFrame,
  renderCompletedCheckFrame,
  renderUnavailableFrame,
} from './matrixEngine';
import { HardwareLightState } from '../types/telemetry';

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function validateFrame(frame: number[][], label: string) {
  assert(Array.isArray(frame), `${label}: frame must be an array`);
  assert(frame.length === ROWS, `${label}: frame must have ${ROWS} rows, got ${frame.length}`);
  for (let r = 0; r < ROWS; r++) {
    assert(Array.isArray(frame[r]), `${label}: row ${r} must be an array`);
    assert(
      frame[r].length === COLS,
      `${label}: row ${r} must have ${COLS} columns, got ${frame[r].length}`
    );
    for (let c = 0; c < COLS; c++) {
      const val = frame[r][c];
      assert(
        Number.isInteger(val) && val >= 0 && val <= MAX_BRIGHTNESS,
        `${label}: pixel [${r}, ${c}] must be 0..${MAX_BRIGHTNESS}, got ${val}`
      );
    }
  }
}

export function runMatrixEngineTests(): { passed: number; total: number } {
  let passed = 0;
  let total = 0;

  function test(name: string, fn: () => void) {
    total++;
    try {
      fn();
      passed++;
      console.log(`✓ ${name}`);
    } catch (e: any) {
      console.error(`✗ ${name}: ${e.message}`);
      throw e;
    }
  }

  test('emptyFrame generates 8x13 zeroed matrix', () => {
    const f = emptyFrame();
    validateFrame(f, 'emptyFrame');
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        assert(f[r][c] === 0, `emptyFrame pixel [${r}, ${c}] must be 0`);
      }
    }
  });

  test('all percentage values 0..100 produce valid 8x13 frames', () => {
    for (let p = 0; p <= 100; p++) {
      const standard = renderPercentageFrame(p);
      validateFrame(standard, `renderPercentageFrame(${p})`);

      const charging = renderPercentageFrame(p, { charging: true, pulseStep: p % 13 });
      validateFrame(charging, `renderPercentageFrame(${p}, charging)`);

      const slow = renderPercentageFrame(p, { slow: true });
      validateFrame(slow, `renderPercentageFrame(${p}, slow)`);
    }
  });

  test('special glyph frames (heart, dots, stall, failed, completed, unavailable) are valid', () => {
    validateFrame(renderHeartFrame(5, 50), 'renderHeartFrame');
    validateFrame(renderWaitingDotsFrame(0, 30), 'renderWaitingDotsFrame dot 0');
    validateFrame(renderWaitingDotsFrame(1, 30, true), 'renderWaitingDotsFrame dot 1 slow');
    validateFrame(renderWaitingDotsFrame(2, 30), 'renderWaitingDotsFrame dot 2');
    validateFrame(renderStallFrame(true, 40), 'renderStallFrame blinkOn');
    validateFrame(renderStallFrame(false, 40), 'renderStallFrame blinkOff');
    validateFrame(renderFailedFrame(), 'renderFailedFrame');
    validateFrame(renderCompletedCheckFrame(), 'renderCompletedCheckFrame');
    validateFrame(renderUnavailableFrame(), 'renderUnavailableFrame');
  });

  test('selectDisplayFrame handles all hardware states and elapsed time increments', () => {
    const states: HardwareLightState[] = [
      'idle',
      'running',
      'slow',
      'suspected_stall',
      'failed',
      'completed',
      'battery',
      'battery_charging',
      'battery_unavailable',
      'download',
    ];

    for (const st of states) {
      for (const ms of [0, 500, 1500, 3000, 7500, 12000]) {
        for (const prog of [0, 42, 100]) {
          const res = selectDisplayFrame(st, prog, ms, true);
          validateFrame(res.frame, `selectDisplayFrame(${st}, ${prog}, ${ms})`);
          assert(typeof res.description === 'string' && res.description.length > 0, 'Must have description');
          assert(typeof res.led3.color === 'string' && res.led3.color.length > 0, 'Must have LED3 color');
        }
      }
    }
  });

  return { passed, total };
}

// Auto-run if executed in node
if (typeof process !== 'undefined' && process.argv && process.argv[1]?.includes('matrixEngine.test')) {
  console.log('Running Matrix Engine test suite...');
  const res = runMatrixEngineTests();
  console.log(`\nAll ${res.passed}/${res.total} tests passed successfully!`);
}
