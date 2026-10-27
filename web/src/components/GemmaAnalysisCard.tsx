import React from 'react';
import { GemmaCardModel } from '../lib/gemmaCard';

interface GemmaAnalysisCardProps {
  model: GemmaCardModel;
}

const severityTone: Record<string, string> = {
  info: 'bg-sky-600',
  warning: 'bg-amber-600',
  error: 'bg-red-600',
  critical: 'bg-red-800',
};

export const GemmaAnalysisCard: React.FC<GemmaAnalysisCardProps> = ({ model }) => {
  const tone = severityTone[model.severity] || 'bg-red-600';
  return (
    <div className="arch-cell p-5 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase text-white ${tone}`}>
            {model.title}
          </span>
          <span className="text-xs font-mono uppercase tracking-wide text-[#787C82]">
            {model.failureStatus}
          </span>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase ${
            model.verified
              ? 'bg-emerald-600 text-white'
              : 'bg-amber-500 text-[#141517]'
          }`}
        >
          {model.verificationLabel}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div>
            <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Diagnosis</div>
            <p className="text-sm font-semibold text-[#141517] dark:text-white">{model.diagnosis}</p>
          </div>
          <div className="flex flex-wrap gap-6">
            <div>
              <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Confidence</div>
              <p className="font-mono text-sm font-bold text-[#141517] dark:text-white">
                {model.confidenceLabel}
              </p>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Severity</div>
              <p className="font-mono text-sm font-bold uppercase text-[#141517] dark:text-white">
                {model.severity}
              </p>
            </div>
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Recommended action</div>
            <p className="text-sm text-[#141517] dark:text-white">{model.recommendedAction}</p>
          </div>
          {model.fallbackSummary && !model.verified && (
            <div>
              <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Rules fallback</div>
              <p className="text-sm text-[#4A4D52] dark:text-[#D1D5DB]">{model.fallbackSummary}</p>
            </div>
          )}
        </div>

        <div>
          <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">Evidence</div>
          {model.evidence.length === 0 ? (
            <pre className="p-3.5 rounded-lg bg-[#141517] text-amber-200 font-mono text-xs whitespace-pre-wrap">
              No log line was cited.
            </pre>
          ) : (
            <div className="space-y-2">
              {model.evidence.map((item) => (
                <div key={`${item.logLine}-${item.reason}`}>
                  <pre className="p-3.5 rounded-lg bg-[#141517] text-emerald-200 font-mono text-xs whitespace-pre-wrap">
                    {item.logLine}
                  </pre>
                  {item.reason && (
                    <p className="mt-1 text-[11px] text-[#4A4D52] dark:text-[#9CA3AF]">{item.reason}</p>
                  )}
                  {!item.found && (
                    <p className="mt-1 text-[11px] font-semibold text-amber-700 dark:text-amber-300">
                      Not found in the logs sent to Gemma.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-[#4A4D52] dark:text-[#9CA3AF]">
            {model.whyOpen}
          </p>
        </div>
      </div>
    </div>
  );
};
