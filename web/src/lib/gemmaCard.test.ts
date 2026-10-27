import { gemmaCardModel, WHY_OPEN } from './gemmaCard';
import { FailureExplanation } from '../types/telemetry';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const verified: FailureExplanation = {
  category: 'network_error',
  summary: 'Network connection error (ConnectionRefusedError)',
  suggestion: 'Check internet connection, DNS resolution, and target server availability.',
  confidence: 0.92,
  source: 'gemma',
  severity: 'error',
  verification_status: 'verified',
  diagnosis: 'The socket connection was refused.',
  recommended_action: 'Check that the UNO Q receiver is listening.',
  evidence: [
    {
      log_line: 'ConnectionRefusedError: [Errno 61] Connection refused',
      reason: 'This line is the failing call.',
      found: true,
    },
  ],
};

const card = gemmaCardModel(verified, 'failed');
assert(card !== null, 'verified explanation should produce a card');
assert(card!.title === 'Gemma Failure Analysis', 'title');
assert(card!.diagnosis === 'The socket connection was refused.', 'diagnosis');
assert(
  card!.evidence[0].logLine === 'ConnectionRefusedError: [Errno 61] Connection refused',
  'evidence line'
);
assert(card!.diagnosis !== card!.evidence[0].logLine, 'diagnosis is separate from evidence');
assert(card!.confidenceLabel === '92%', 'confidence');
assert(card!.severity === 'error', 'severity');
assert(card!.verificationLabel === 'Evidence verified', 'verified label');
assert(card!.verified === true, 'verified flag');
assert(card!.recommendedAction.includes('receiver'), 'action');
assert(card!.whyOpen === WHY_OPEN, 'why open');

const unverified = gemmaCardModel(
  {
    ...verified,
    verification_status: 'unverified',
    evidence: [
      {
        log_line: 'ConnectionError: receiver unavailable after 99 retries',
        reason: 'not in the log',
        found: false,
      },
    ],
    fallback_summary: 'Network connection error (ConnectionRefusedError)',
  },
  'failed'
);
assert(unverified !== null && unverified.verified === false, 'unverified is not success');
assert(unverified!.verificationLabel === 'Evidence unverified', 'unverified label');
assert(unverified!.evidence[0].found === false, 'missing evidence stays visible');

assert(gemmaCardModel({ ...verified, verification_status: undefined }, 'failed') === null, 'rules card stays on the old panel');

const timeout = gemmaCardModel(
  { ...verified, verification_status: 'timeout', evidence: [], source: 'fallback' },
  'suspected_stall'
);
assert(timeout!.verificationLabel === 'Gemma timed out', 'timeout label');
assert(timeout!.failureStatus === 'suspected_stall', 'stall status');
assert(timeout!.verified === false, 'timeout is not verified');

console.log('gemmaCard tests passed');
