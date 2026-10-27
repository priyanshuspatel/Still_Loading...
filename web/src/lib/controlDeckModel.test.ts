import {
  CONTROL_BUTTONS,
  buttonDisabled,
  controlPath,
  feedLine,
  gemmaUnavailableCopy,
  matrixReadout,
  mergeFeed,
  modeLabel,
  optimisticCommand,
  unoStatusLabel,
  ControlSnapshot,
} from './controlDeckModel.ts';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const actions = CONTROL_BUTTONS.map((button) => button.action);
assert(actions.includes('battery'), 'battery button');
assert(actions.includes('download'), 'download button');
assert(actions.includes('job_failure'), 'failed job button');
assert(actions.includes('reset'), 'reset button');
assert(actions.includes('gemma'), 'gemma button');
assert(actions.includes('connection'), 'connection button');
const labels = CONTROL_BUTTONS.map((button) => button.label);
assert(!labels.includes('Slow'), 'slow button removed');
assert(!labels.includes('Stall'), 'stall button removed');
assert(!labels.includes('Auto Mode'), 'auto mode button removed');
assert(!labels.includes('Job Mode'), 'job mode button removed');
assert(!labels.includes('Start Camera'), 'camera button removed');

const expectedPaths: Record<string, string> = {
  battery: '/v1/control/battery',
  download: '/v1/control/download',
  job_success: '/v1/control/job',
  job_failure: '/v1/control/job',
  completed: '/v1/control/job',
  idle: '/v1/control/idle',
  reset: '/v1/control/reset',
  stop: '/v1/control/stop',
  demo: '/v1/control/demo',
  gemma: '/v1/control/gemma',
  connection: '/v1/control/connection',
};

for (const action of actions) {
  const target = controlPath(action);
  assert(!('command' in target.body), `${action} must not send a command`);
  assert(!('argv' in target.body), `${action} must not send argv`);
  assert(!('shell' in target.body), `${action} must not send a shell`);
  assert(target.path === expectedPaths[action], `${action} path ${target.path}`);
}

assert(buttonDisabled('battery', true), 'battery waits while another operation runs');
assert(!buttonDisabled('stop', true), 'stop stays available');
assert(modeLabel('auto') === 'AUTO MODE', 'auto mode label');
assert(modeLabel('job') === 'JOB MODE', 'job mode label');

const batteryView = {
  uno_q: 'connected',
  lights: { state: 'battery', code: 6, progress: 87, progress_known: true, display_mode: 'battery', charging_state: 'discharging' },
  battery: { available: true, percent: 87, charging_state: 'discharging' },
  download: { active: false, state: 'idle', progress: 0 },
} as ControlSnapshot;
assert(matrixReadout(batteryView) === 'Battery 87% discharging', 'battery readout uses the light state');
const demoView = { ...batteryView, demo: { simulated: true }, matrix: { simulated: true } } as ControlSnapshot;
assert(matrixReadout(demoView).startsWith('DEMO / SIMULATED'), 'demo readout is labeled');

const optimistic = optimisticCommand('battery', new Date('2026-10-27T11:04:21Z'));
assert(optimistic.source === 'COMMAND', 'command source');
assert(optimistic.action.includes('Battery'), 'battery label');
assert(optimistic.pending === true, 'pending until the backend answers');

const merged = mergeFeed(
  [optimistic].filter((event) => event.id !== optimistic.id),
  [
    {
      id: 1,
      timestamp: '11:04:21',
      source: 'COMMAND',
      action: 'battery requested',
    },
    {
      id: 2,
      timestamp: '11:04:21',
      source: 'BATTERY',
      action: '82% discharging',
    },
  ]
);
assert(merged.length === 2, 'server events replace the optimistic row');
assert(merged[0].source === 'COMMAND', 'command acknowledgement stays');
assert(merged[1].source === 'BATTERY', 'battery result stays in the feed');
assert(feedLine(merged[1]) === '11:04:21  BATTERY  82% discharging', 'feed line');
assert(unoStatusLabel('connected') === 'UNO Q ● CONNECTED', 'connected label');
assert(unoStatusLabel('offline') === 'UNO Q ● OFFLINE', 'offline label');
assert(
  gemmaUnavailableCopy({ verification_status: 'unavailable' }) ===
    'Gemma unavailable — rules explanation used',
  'gemma fallback copy'
);
assert(gemmaUnavailableCopy({ verification_status: 'verified' }) === null, 'verified has no fallback banner');

console.log('controlDeckModel tests ok');
