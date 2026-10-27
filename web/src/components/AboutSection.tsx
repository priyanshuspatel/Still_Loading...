import React from 'react';

export const AboutSection: React.FC = () => {
  return (
    <section
      id="about"
      className="py-16 sm:py-24 bg-[#F1F0EC] dark:bg-[#131519] border-b border-black/[0.08] dark:border-white/[0.08]"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-6 space-y-2">
            <div className="text-xs font-mono uppercase tracking-wider text-[#0055FF] dark:text-[#38BDF8] font-semibold">
              Design Philosophy
            </div>
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-[-0.035em] text-[#141517] dark:text-white leading-[1.05]">
              Stop staring.{' '}
              <span className="font-serif italic font-normal text-[#4A4D52] dark:text-[#9CA3AF]">
                Start living.
              </span>
            </h2>
          </div>

          <p className="lg:col-span-6 text-sm sm:text-base text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
            Digital progress is invisible until you break focus to check a screen. Still Loading pairs macOS system telemetry with 104 discrete blue LEDs so your computer can do the waiting while you step away from your desk.
          </p>
        </div>

        <div className="arch-grid grid grid-cols-1 md:grid-cols-3">
          <div className="arch-cell p-6 sm:p-8 space-y-2.5">
            <div className="text-xs font-mono text-[#0055FF] dark:text-[#38BDF8] font-bold">
              01 // TANGIBLE PHOTONS
            </div>
            <h3 className="text-lg font-bold text-[#141517] dark:text-white">
              Physical 3-Bit Luminance
            </h3>
            <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
              Abstract percentages become physical 3-bit grayscale light on an 8×13 matrix, paired with semantic state color on RGB LED 3.
            </p>
          </div>

          <div className="arch-cell p-6 sm:p-8 space-y-2.5">
            <div className="text-xs font-mono text-[#0055FF] dark:text-[#38BDF8] font-bold">
              02 // LOCAL-FIRST HONESTY
            </div>
            <h3 className="text-lg font-bold text-[#141517] dark:text-white">
              Zero Fabricated Progress
            </h3>
            <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
              Zero cloud lock-in and zero fake percentages. Indeterminate jobs show stepping dots; secrets are redacted before leaving your Mac.
            </p>
          </div>

          <div className="arch-cell p-6 sm:p-8 space-y-2.5">
            <div className="text-xs font-mono text-[#0055FF] dark:text-[#38BDF8] font-bold">
              03 // CALM COMPUTING
            </div>
            <h3 className="text-lg font-bold text-[#141517] dark:text-white">
              Peripheral Awareness
            </h3>
            <p className="text-sm text-[#4A4D52] dark:text-[#9CA3AF] leading-relaxed">
              Gentle breathing pulses, stepping dots, and optional harmonic chimes inform your periphery without demanding your focus.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
