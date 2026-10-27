import { FailureExplanation } from '../types/telemetry';

export interface GemmaCardModel {
  title: string;
  failureStatus: string;
  diagnosis: string;
  confidenceLabel: string;
  severity: string;
  evidence: { logLine: string; reason: string; found: boolean }[];
  recommendedAction: string;
  verificationLabel: string;
  verificationStatus: string;
  verified: boolean;
  fallbackSummary: string;
  whyOpen: string;
}

const STATUS_LABELS: Record<string, string> = {
  verified: 'Evidence verified',
  unverified: 'Evidence unverified',
  unavailable: 'Gemma unavailable',
  timeout: 'Gemma timed out',
  malformed: 'Malformed model response',
};

export const WHY_OPEN =
  "Gemma's explanation is not trusted merely because the model said it. The log line is the evidence that was checked against the text sent to the model.";

export function gemmaCardModel(
  explanation: FailureExplanation | null | undefined,
  failureStatus: string
): GemmaCardModel | null {
  if (!explanation?.verification_status) return null;
  const status = explanation.verification_status;
  const confidence =
    typeof explanation.confidence === 'number' ? explanation.confidence : 0;
  const clamped = Math.max(0, Math.min(1, confidence));
  return {
    title: 'Gemma Failure Analysis',
    failureStatus,
    diagnosis: explanation.diagnosis || explanation.summary,
    confidenceLabel: `${Math.round(clamped * 100)}%`,
    severity: explanation.severity || 'error',
    evidence: (explanation.evidence || []).map((item) => ({
      logLine: item.log_line,
      reason: item.reason,
      found: item.found !== false,
    })),
    recommendedAction: explanation.recommended_action || explanation.suggestion,
    verificationLabel: STATUS_LABELS[status] || 'Evidence unverified',
    verificationStatus: status,
    verified: status === 'verified',
    fallbackSummary: explanation.fallback_summary || '',
    whyOpen: WHY_OPEN,
  };
}
