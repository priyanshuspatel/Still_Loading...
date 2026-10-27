import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Filter,
} from 'lucide-react';
import { JobHistoryRecord, HistoryStats } from '../types/telemetry';
import { DEMO_JOB_HISTORY, DEMO_HISTORY_STATS } from '../lib/demoData';
import { formatRelativeTime } from '../lib/telemetryClient';
import { gemmaCardModel } from '../lib/gemmaCard';
import { GemmaAnalysisCard } from './GemmaAnalysisCard';

interface JobHistoryProps {
  isLiveMode: boolean;
  liveJobs?: JobHistoryRecord[];
  liveStats?: HistoryStats;
}

export const JobHistory: React.FC<JobHistoryProps> = ({
  isLiveMode,
  liveJobs,
  liveStats,
}) => {
  const [failedOnly, setFailedOnly] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [copiedFixId, setCopiedFixId] = useState<string | null>(null);

  const jobs: JobHistoryRecord[] =
    isLiveMode && liveJobs ? liveJobs : DEMO_JOB_HISTORY;
  const stats: HistoryStats =
    isLiveMode && liveStats ? liveStats : DEMO_HISTORY_STATS;

  const filteredJobs = failedOnly ? jobs.filter((j) => j.is_failure) : jobs;

  const handleCopyFix = (text: string, jobId: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedFixId(jobId);
      setTimeout(() => setCopiedFixId(null), 2000);
    }
  };

  const toggleExpand = (jobId: string) => {
    setExpandedJobId(expandedJobId === jobId ? null : jobId);
  };

  const topCategory = Object.entries(stats.failure_categories || {}).sort(
    (a, b) => b[1] - a[1]
  )[0]?.[0];

  const maxDuration = Math.max(
    1,
    ...jobs.map((j) => j.duration_seconds || 1)
  );

  return (
    <section className="pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      <div className="arch-grid">
        {/* Header Row */}
        <div className="arch-cell p-5 sm:px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold tracking-tight text-[#141517] dark:text-white">
                SQLite Session Archive
              </h2>
              <span className="text-xs font-mono text-[#787C82]">
                // history_store.py
              </span>
            </div>
            <p className="text-xs text-[#787C82]">
              Persistent build durations, monotonic sequence counts, and failure explanations
            </p>
          </div>

          <button
            onClick={() => setFailedOnly(!failedOnly)}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all self-start sm:self-auto ${
              failedOnly
                ? 'bg-red-600 text-white'
                : 'bg-[#F1F0EC] dark:bg-white/10 text-[#141517] dark:text-white'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            <span>{failedOnly ? 'Failed Runs Only' : 'Filter: Failed Runs'}</span>
          </button>
        </div>

        {/* 4-Column Hairline KPI Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-[1px] bg-black/[0.08] dark:bg-white/[0.08]">
          <div className="arch-cell-stone p-4 sm:p-5">
            <div className="text-[11px] font-mono uppercase text-[#787C82]">
              Monitored Runs
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[#141517] dark:text-white my-1">
              {stats.total_jobs}
            </div>
            <div className="text-[11px] text-[#787C82]">
              {stats.completed_count} passed • {stats.failed_count} failed
            </div>
          </div>

          <div className="arch-cell-stone p-4 sm:p-5">
            <div className="text-[11px] font-mono uppercase text-[#787C82]">
              Success Rate
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400 my-1">
              {stats.success_rate}%
            </div>
            <div className="text-[11px] text-[#787C82]">
              Verified exit code 0
            </div>
          </div>

          <div className="arch-cell-stone p-4 sm:p-5">
            <div className="text-[11px] font-mono uppercase text-[#787C82]">
              Mean Duration
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[#141517] dark:text-white my-1">
              {stats.avg_duration_seconds}s
            </div>
            <div className="text-[11px] text-[#787C82]">
              {stats.total_duration_seconds}s total
            </div>
          </div>

          <div className="arch-cell-stone p-4 sm:p-5">
            <div className="text-[11px] font-mono uppercase text-[#787C82]">
              Primary Failure Class
            </div>
            <div className="text-base sm:text-lg font-extrabold font-mono text-red-600 dark:text-red-400 uppercase truncate my-1.5">
              {topCategory ? topCategory.replace(/_/g, ' ') : 'None'}
            </div>
            <div className="text-[11px] text-[#787C82]">
              Rules-first classifier
            </div>
          </div>
        </div>

        {/* Execution Ledger Rows */}
        <div className="arch-cell divide-y divide-black/[0.06] dark:divide-white/[0.08]">
          {filteredJobs.map((job) => {
            const isExpanded = expandedJobId === job.job_id;
            const hasFailureDetails =
              job.is_failure && (job.explanation || job.excerpt || job.message);
            const durationPct = Math.round(
              (job.duration_seconds / maxDuration) * 100
            );
            const gemmaAnalysis = gemmaCardModel(
              job.explanation,
              job.is_failure ? 'failed' : job.event
            );

            return (
              <div key={job.job_id}>
                <div
                  onClick={() => hasFailureDetails && toggleExpand(job.job_id)}
                  className={`p-4 sm:px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                    hasFailureDetails
                      ? 'cursor-pointer hover:bg-[#F1F0EC]/60 dark:hover:bg-white/[0.02]'
                      : ''
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${
                        job.is_failure ? 'bg-red-600' : 'bg-emerald-500'
                      }`}
                    />
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-bold text-[#141517] dark:text-white">
                          {job.job_id}
                        </span>
                        {job.is_failure && job.category && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-red-500/15 text-red-700 dark:text-red-300">
                            {job.category.replace(/_/g, ' ')}
                          </span>
                        )}
                        {hasFailureDetails && (
                          <span className="text-xs text-[#0055FF] dark:text-[#38BDF8] font-medium">
                            {isExpanded ? 'Hide diagnosis' : 'Inspect failure →'}
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-mono text-[#787C82]">
                        {formatRelativeTime(job.end_time)} • {job.accepted_count} events (seq #{job.highest_sequence})
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono">
                    <div className="hidden md:flex items-center w-28">
                      <div className="w-full h-1.5 rounded-sm bg-black/[0.07] dark:bg-white/10 overflow-hidden">
                        <div
                          className={`h-full ${
                            job.is_failure ? 'bg-red-500' : 'bg-[#141517] dark:bg-[#38BDF8]'
                          }`}
                          style={{ width: `${Math.max(10, durationPct)}%` }}
                        />
                      </div>
                    </div>

                    <span className="text-[#4A4D52] dark:text-[#9CA3AF] w-14 text-right">
                      {job.duration_seconds.toFixed(1)}s
                    </span>

                    <span
                      className={`px-2 py-0.5 rounded font-bold ${
                        job.is_failure
                          ? 'bg-red-500/10 text-red-700 dark:text-red-300'
                          : 'bg-[#F1F0EC] dark:bg-white/10 text-[#4A4D52] dark:text-[#9CA3AF]'
                      }`}
                    >
                      Exit {job.exit_code ?? 0}
                    </span>

                    {hasFailureDetails && (
                      <div className="text-[#787C82]">
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {isExpanded && hasFailureDetails && gemmaAnalysis && (
                  <div className="px-4 pb-4">
                    <GemmaAnalysisCard model={gemmaAnalysis} />
                  </div>
                )}

                {isExpanded && hasFailureDetails && !gemmaAnalysis && (
                  <div className="px-6 pb-5 pt-2 bg-[#F1F0EC]/70 dark:bg-[#131519] border-t border-black/[0.06] dark:border-white/10">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
                      <div className="space-y-2.5">
                        <div className="p-3.5 rounded-lg bg-white dark:bg-[#181B20] border border-black/[0.06] dark:border-white/10">
                          <div className="text-[10px] font-mono uppercase text-[#787C82] mb-1">
                            Root Cause Diagnosis
                          </div>
                          <p className="text-xs font-bold text-red-600 dark:text-red-400">
                            {job.explanation?.summary ||
                              job.summary ||
                              job.message ||
                              'Process terminated with non-zero exit code.'}
                          </p>
                        </div>

                        {(job.explanation?.suggestion || job.suggestion) && (
                          <div className="p-3.5 rounded-lg bg-white dark:bg-[#181B20] border border-black/[0.06] dark:border-white/10 flex items-center justify-between gap-2">
                            <code className="text-xs font-mono font-bold text-[#0055FF] dark:text-[#38BDF8] truncate">
                              {job.explanation?.suggestion || job.suggestion}
                            </code>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCopyFix(
                                  job.explanation?.suggestion ||
                                    job.suggestion ||
                                    '',
                                  job.job_id
                                );
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#141517] text-white text-[11px] font-semibold shrink-0"
                            >
                              {copiedFixId === job.job_id ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  <span>Copied</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3" />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                        )}
                      </div>

                      <pre className="p-3.5 rounded-lg bg-[#141517] text-slate-200 font-mono text-xs overflow-x-auto whitespace-pre-wrap select-text">
                        {job.excerpt || 'No log excerpt captured.'}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
