import { renderToStaticMarkup } from 'react-dom/server';
import { ControlDeck } from './ControlDeck.tsx';
import { ControlSnapshot } from '../lib/controlDeckModel.ts';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const state: ControlSnapshot = {
  uno_q: 'offline',
  lights: { state: 'failed', code: 4, progress: 20, progress_known: true, display_mode: 'job' },
  battery: { available: true, percent: 82, charging_state: 'discharging', simulated: false },
  download: {
    active: false,
    state: 'idle',
    progress: 0,
    progress_known: false,
    downloaded_bytes: 0,
    total_bytes: null,
  },
  job: {
    is_failure: true,
    excerpt: "ModuleNotFoundError: No module named 'numpy'",
    explanation: null,
  },
  gemma: {
    category: 'missing_dependency',
    summary: 'Missing module',
    suggestion: 'pip install numpy',
    confidence: 0.5,
    source: 'rules',
    severity: 'error',
    verification_status: 'unavailable',
    diagnosis: 'Missing module',
    recommended_action: 'pip install numpy',
    evidence: [],
    fallback_summary: 'Missing module',
  },
  events: [
    { id: 1, timestamp: '11:04:21', source: 'COMMAND', action: 'Failed requested' },
    { id: 2, timestamp: '11:04:22', source: 'GEMMA', action: 'Gemma unavailable — rules explanation used' },
  ],
  demo: { simulated: false },
};

const html = renderToStaticMarkup(
  <ControlDeck autoPoll={false} initialState={state} presentationDefault />
);

assert(html.includes('Control Deck'), 'title renders');
assert(html.includes('UNO Q ● OFFLINE'), 'offline indicator renders');
assert(html.includes('data-action="battery"'), 'battery button renders');
assert(html.includes('data-action="download"'), 'download button renders');
assert(html.includes('data-action="job_failure"'), 'failed button renders');
assert(html.includes('data-action="reset"'), 'reset button renders');
assert(!html.includes('data-action="job_slow"'), 'slow button removed');
assert(!html.includes('data-action="job_stall"'), 'stall button removed');
assert(!html.includes('data-action="auto"'), 'auto mode button removed');
assert(!html.includes('data-action="job_mode"'), 'job mode button removed');
assert(!html.includes('UNO Q LIVE CAMERA'), 'camera block removed');
assert(!html.includes('Start Camera'), 'camera button removed');
assert(html.includes('11:04:21'), 'event feed renders');
assert(html.includes('Gemma unavailable — rules explanation used'), 'gemma fallback renders');
assert(html.includes('Evidence'), 'gemma card renders evidence');
assert(!html.includes('state=failed'), 'presentation mode hides the developer light line');

console.log('ControlDeck render tests ok');
