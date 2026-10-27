/**
 * audioCues.ts — Web Audio API ambient sound synthesizer for Still Loading…
 *
 * Plays short, tasteful synthesized chimes in the browser that match the
 * macOS afplay cues used by the Mac agent.  Zero audio files are fetched;
 * every sound is built from oscillators so the site works offline.
 *
 * Cue semantics
 * -------------
 * completed  → warm descending two-tone chime (mirrors Glass.aiff feel)
 * failed     → low, muted thud — single sine pulse at 80 Hz (mirrors Basso)
 * stall      → two light high taps at 1200 Hz (mirrors Tink × 2)
 *
 * Usage
 * -----
 * import { audioCues } from './audioCues';
 *
 * audioCues.enable();            // call once after a user gesture
 * audioCues.playCompleted();
 * audioCues.playFailed();
 * audioCues.playStall();
 * audioCues.isEnabled();         // → boolean
 * audioCues.toggle();            // flip enabled/disabled; returns new state
 */

// ---------------------------------------------------------------------------
// AudioContext singleton — created lazily on first use after user gesture
// ---------------------------------------------------------------------------

let _ctx: AudioContext | null = null;
let _enabled = false;

function getCtx(): AudioContext | null {
  if (!_enabled) return null;
  if (!_ctx) {
    try {
      _ctx = new AudioContext();
    } catch {
      return null;
    }
  }
  // Resume if suspended (browser autoplay policy)
  if (_ctx.state === 'suspended') {
    _ctx.resume().catch(() => undefined);
  }
  return _ctx;
}

// ---------------------------------------------------------------------------
// Low-level tone builder
// ---------------------------------------------------------------------------

interface ToneParams {
  frequency: number;
  /** oscillator type */
  type: OscillatorType;
  /** seconds from now to start */
  startOffset: number;
  /** total duration of this tone in seconds */
  duration: number;
  /** peak gain (0–1) */
  gain: number;
  /** attack time in seconds */
  attack: number;
  /** release time in seconds */
  release: number;
}

function scheduleTone(ctx: AudioContext, params: ToneParams): void {
  const { frequency, type, startOffset, duration, gain, attack, release } = params;
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(frequency, now + startOffset);

  // Envelope: attack → sustain → release
  const startTime = now + startOffset;
  const peakTime = startTime + attack;
  const releaseStart = startTime + duration - release;
  const endTime = startTime + duration;

  gainNode.gain.setValueAtTime(0, startTime);
  gainNode.gain.linearRampToValueAtTime(gain, peakTime);
  gainNode.gain.setValueAtTime(gain, Math.max(peakTime, releaseStart));
  gainNode.gain.linearRampToValueAtTime(0, endTime);

  osc.connect(gainNode);
  gainNode.connect(ctx.destination);

  osc.start(startTime);
  osc.stop(endTime + 0.01);
}

// ---------------------------------------------------------------------------
// Named cues
// ---------------------------------------------------------------------------

/** Warm descending two-tone chime — mirrors Glass.aiff */
function playCompleted(): void {
  const ctx = getCtx();
  if (!ctx) return;

  // High note then lower note, both sine, gentle
  scheduleTone(ctx, {
    frequency: 880,
    type: 'sine',
    startOffset: 0,
    duration: 0.25,
    gain: 0.35,
    attack: 0.01,
    release: 0.12,
  });
  scheduleTone(ctx, {
    frequency: 660,
    type: 'sine',
    startOffset: 0.2,
    duration: 0.35,
    gain: 0.28,
    attack: 0.01,
    release: 0.2,
  });
}

/** Low muted thud — mirrors Basso.aiff */
function playFailed(): void {
  const ctx = getCtx();
  if (!ctx) return;

  scheduleTone(ctx, {
    frequency: 80,
    type: 'sine',
    startOffset: 0,
    duration: 0.3,
    gain: 0.5,
    attack: 0.005,
    release: 0.25,
  });
  // Subtle sub-harmonic layer for weight
  scheduleTone(ctx, {
    frequency: 55,
    type: 'triangle',
    startOffset: 0,
    duration: 0.25,
    gain: 0.2,
    attack: 0.005,
    release: 0.2,
  });
}

/** Two light high taps — mirrors Tink × 2 */
function playStall(): void {
  const ctx = getCtx();
  if (!ctx) return;

  for (let i = 0; i < 2; i++) {
    scheduleTone(ctx, {
      frequency: 1200,
      type: 'sine',
      startOffset: i * 0.18,
      duration: 0.1,
      gain: 0.25,
      attack: 0.002,
      release: 0.08,
    });
  }
}

/** Play a cue by name. Unknown names are silently ignored. */
function playCue(name: 'completed' | 'failed' | 'stall'): void {
  switch (name) {
    case 'completed': return playCompleted();
    case 'failed':    return playFailed();
    case 'stall':     return playStall();
  }
}

// ---------------------------------------------------------------------------
// Enable / disable control
// ---------------------------------------------------------------------------

/** Enable audio output. Must be called from a user-gesture handler. */
function enable(): void {
  _enabled = true;
  // Eagerly create context while inside the gesture
  getCtx();
}

/** Disable audio output. No sounds will play until re-enabled. */
function disable(): void {
  _enabled = false;
}

/** Return whether audio cues are currently enabled. */
function isEnabled(): boolean {
  return _enabled;
}

/**
 * Toggle enabled state.
 * @returns The new enabled state after toggling.
 */
function toggle(): boolean {
  if (_enabled) {
    disable();
  } else {
    enable();
  }
  return _enabled;
}

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

export const audioCues = {
  enable,
  disable,
  isEnabled,
  toggle,
  playCue,
  playCompleted,
  playFailed,
  playStall,
} as const;
